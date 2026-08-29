import { useEffect, useState } from "react";
import { api, type AuditEvent, type TransactionSummary } from "../services/api";
import { formatINR, formatTime } from "../services/format";
import { Card, Empty, ErrorBanner, Pill, statusTone } from "../components/ui";

/**
 * Agent activity / audit dashboard (US-9).
 *
 * Completeness is the point here, not polish: every state transition, every
 * agent, every failure path, with the reasoning attached. Selecting a
 * transaction shows its full ordered timeline.
 */

const AGENT_TONE: Record<string, string> = {
  human: "info",
  buyer_agent: "info",
  merchant_agent: "info",
  policy_engine: "warn",
  permission_system: "warn",
  trust_engine: "mute",
  razorpay: "pass",
  system: "mute",
};

const DRILLS = [
  { id: "policy-violation", label: "Policy violation", hint: "Over-limit purchase → BLOCKED, Razorpay never called" },
  { id: "payment-timeout", label: "Payment timeout", hint: "Unknown state → verify, never blind-retry" },
  { id: "duplicate-webhook", label: "Duplicate webhook", hint: "Replay the same event_id → ignored once seen" },
  { id: "tampered-webhook", label: "Forged signature", hint: "Bad signature → rejected before parsing" },
] as const;

export default function AuditPage() {
  const [transactions, setTransactions] = useState<TransactionSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [drillResult, setDrillResult] = useState<any>(null);
  const [drillBusy, setDrillBusy] = useState<string | null>(null);

  const load = () =>
    api.auditTransactions().then((t) => {
      setTransactions(t);
      if (!selected && t.length) setSelected(t[0].purchase_intent_id);
    }).catch((e) => setError(String(e)));

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!selected) return;
    api.auditTimeline(selected).then((r) => setEvents(r.events)).catch((e) => setError(String(e)));
  }, [selected]);

  async function runDrill(id: (typeof DRILLS)[number]["id"]) {
    setDrillBusy(id);
    setDrillResult(null);
    try {
      const r = await api.drill(id);
      setDrillResult({ id, r });
      await load();
      if (r?.intent?.intent_id) setSelected(r.intent.intent_id);
      if (r?.purchase_intent_id) setSelected(r.purchase_intent_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setDrillBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <ErrorBanner error={error} />

      <Card
        title="Failure-mode drills"
        subtitle="Each runs the same production code path the real failure would take"
      >
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {DRILLS.map((d) => (
            <button
              key={d.id}
              onClick={() => runDrill(d.id)}
              disabled={drillBusy !== null}
              className="rounded-md border border-edge p-2.5 text-left transition hover:border-accent/60 hover:bg-edge/30 disabled:opacity-50"
            >
              <span className="block text-xs font-medium text-slate-200">
                {drillBusy === d.id ? "Running…" : d.label}
              </span>
              <span className="mt-0.5 block text-[11px] leading-snug text-muted">{d.hint}</span>
            </button>
          ))}
        </div>

        {drillResult && (
          <pre className="mt-3 max-h-64 overflow-auto rounded border border-edge bg-ink p-3 font-mono text-[11px] leading-relaxed text-slate-300">
            {JSON.stringify(drillResult.r, null, 2)}
          </pre>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
        <Card title="Transactions" subtitle={`${transactions.length} recorded`}>
          {transactions.length === 0 ? (
            <Empty>No transactions yet.</Empty>
          ) : (
            <ul className="space-y-1">
              {transactions.map((t) => (
                <li key={t.purchase_intent_id}>
                  <button
                    onClick={() => setSelected(t.purchase_intent_id)}
                    className={`w-full rounded-md border p-2 text-left transition ${
                      selected === t.purchase_intent_id
                        ? "border-accent bg-accent/10"
                        : "border-edge hover:bg-edge/40"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-slate-200">{formatINR(t.amount)}</span>
                      <Pill tone={statusTone(t.status)}>{t.status}</Pill>
                    </div>
                    <p className="mt-0.5 truncate text-[11px] text-muted">{t.product_id}</p>
                    <p className="text-[11px] text-muted">{t.event_count} events</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Timeline"
          subtitle={selected ?? "Select a transaction"}
          right={<Pill tone="mute">{events.length} events</Pill>}
        >
          {events.length === 0 ? (
            <Empty>No events for this transaction.</Empty>
          ) : (
            <ol className="relative space-y-2 border-l border-edge pl-4">
              {events.map((e) => (
                <li key={e.event_id} className="relative">
                  <span
                    className={`absolute -left-[21px] top-1.5 h-2 w-2 rounded-full ${
                      e.status === "BLOCKED" || e.status === "FAILED" || e.status === "DENIED"
                        ? "bg-fail"
                        : e.status === "PENDING" || e.status === "IGNORED"
                          ? "bg-warn"
                          : "bg-pass"
                    }`}
                  />
                  <details className="rounded-md border border-edge/60 p-2">
                    <summary className="cursor-pointer list-none">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] text-muted">
                          {formatTime(e.timestamp)}
                        </span>
                        <Pill tone={AGENT_TONE[e.agent_id] ?? "mute"}>{e.agent_id}</Pill>
                        <code className="font-mono text-[11px] font-semibold text-slate-200">
                          {e.action}
                        </code>
                        {e.status !== "OK" && <Pill tone={statusTone(e.status)}>{e.status}</Pill>}
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-slate-300">{e.reason}</p>
                    </summary>

                    {(e.input_reference || e.output_reference || e.policy_result) && (
                      <div className="mt-2 space-y-2">
                        {e.policy_result && (
                          <Detail label="policy_result" data={e.policy_result} />
                        )}
                        {e.input_reference && <Detail label="input" data={e.input_reference} />}
                        {e.output_reference && <Detail label="output" data={e.output_reference} />}
                      </div>
                    )}
                  </details>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}

function Detail({ label, data }: { label: string; data: unknown }) {
  return (
    <div>
      <span className="label">{label}</span>
      <pre className="mt-0.5 max-h-48 overflow-auto rounded border border-edge bg-ink p-2 font-mono text-[10px] leading-relaxed text-slate-400">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
