import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type AuditEvent, type TransactionSummary } from "../services/api";
import { formatINR, formatTime } from "../services/format";
import { useToast } from "../context/ToastContext";
import {
  Card,
  Empty,
  ErrorBanner,
  Pill,
  Skeleton,
  statusTone,
} from "../components/ui";

/**
 * Agent activity / audit dashboard (US-9).
 *
 * Completeness is the point here, not decoration: every state transition,
 * every agent, every failure path, with the reasoning attached. Selecting a
 * transaction shows its full ordered timeline.
 */
const AGENT_TONE: Record<string, string> = {
  human: "brand",
  buyer_agent: "brand",
  merchant_agent: "brand",
  policy_engine: "warn",
  permission_system: "warn",
  trust_engine: "mute",
  razorpay: "ok",
  system: "mute",
};

const DRILLS = [
  {
    id: "policy-violation",
    label: "Policy violation",
    hint: "Over-limit purchase → BLOCKED, Razorpay never called",
  },
  {
    id: "payment-timeout",
    label: "Payment timeout",
    hint: "Unknown state → verify, never blind-retry",
  },
  {
    id: "duplicate-webhook",
    label: "Duplicate webhook",
    hint: "Replay the same event_id → ignored once seen",
  },
  {
    id: "tampered-webhook",
    label: "Forged signature",
    hint: "Bad signature → rejected before parsing",
  },
] as const;

export default function AuditPage() {
  const toast = useToast();
  const [transactions, setTransactions] = useState<TransactionSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drillResult, setDrillResult] = useState<{ id: string; data: any } | null>(null);
  const [drillBusy, setDrillBusy] = useState<string | null>(null);

  const load = useCallback(
    async (autoSelect = true) => {
      try {
        const t = await api.auditTransactions();
        setTransactions(t);
        setError(null);
        if (autoSelect && t.length) {
          setSelected((cur) => cur ?? t[0].purchase_intent_id);
        }
        return t;
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        return [];
      }
    },
    [],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selected) return;
    setEvents(null);
    api
      .auditTimeline(selected)
      .then((r) => setEvents(r.events))
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [selected]);

  async function runDrill(id: (typeof DRILLS)[number]["id"]) {
    setDrillBusy(id);
    setDrillResult(null);
    try {
      const data = await api.drill(id);
      setDrillResult({ id, data });
      await load(false);
      const next = data?.intent?.intent_id ?? data?.purchase_intent_id;
      if (next) setSelected(next);
      toast.success("Drill complete", DRILLS.find((d) => d.id === id)?.hint);
    } catch (e) {
      toast.error("Drill failed", e instanceof ApiError ? e.message : undefined);
    } finally {
      setDrillBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <ErrorBanner error={error} onRetry={() => load()} />

      <Card
        title="Failure-mode drills"
        subtitle="Each runs the same production code path the real failure would take"
      >
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {DRILLS.map((d) => (
            <button
              key={d.id}
              onClick={() => runDrill(d.id)}
              disabled={drillBusy !== null}
              className="group rounded-lg border border-line p-3 text-left transition-all
                         hover:border-brand/50 hover:bg-brand/5 disabled:opacity-50"
            >
              <span className="block text-xs font-medium text-strong">
                {drillBusy === d.id ? "Running…" : d.label}
              </span>
              <span className="mt-0.5 block text-2xs leading-snug text-subtle">{d.hint}</span>
            </button>
          ))}
        </div>

        {drillResult && (
          <pre className="mt-3 max-h-72 overflow-auto rounded-lg border border-line bg-raised p-3 font-mono text-2xs leading-relaxed text-body">
            {JSON.stringify(drillResult.data, null, 2)}
          </pre>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-[20rem_1fr] items-start">
        <Card
          title="Transactions"
          subtitle={transactions ? `${transactions.length} recorded` : undefined}
        >
          {transactions === null ? (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : transactions.length === 0 ? (
            <Empty icon="≡" title="No transactions yet">
              Run the buyer agent or a drill to produce one.
            </Empty>
          ) : (
            <ul className="max-h-[32rem] space-y-1 overflow-y-auto">
              {transactions.map((t) => (
                <li key={t.purchase_intent_id}>
                  <button
                    onClick={() => setSelected(t.purchase_intent_id)}
                    aria-current={selected === t.purchase_intent_id}
                    className={`w-full rounded-lg border p-2.5 text-left transition-all ${
                      selected === t.purchase_intent_id
                        ? "border-brand bg-brand/8 ring-1 ring-inset ring-brand/20"
                        : "border-line hover:bg-raised"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-medium text-strong">
                        {formatINR(t.amount)}
                      </span>
                      <Pill tone={statusTone(t.status)}>{t.status}</Pill>
                    </div>
                    <p className="mt-0.5 truncate text-2xs text-subtle">{t.product_id}</p>
                    <p className="text-2xs text-subtle">{t.event_count} events</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Timeline"
          subtitle={selected ? <code className="font-mono">{selected}</code> : "Select a transaction"}
          right={events ? <Pill tone="mute">{events.length} events</Pill> : undefined}
        >
          {events === null ? (
            <div className="space-y-2">
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : events.length === 0 ? (
            <Empty icon="◌">No events recorded for this transaction.</Empty>
          ) : (
            <ol className="relative space-y-2 border-l border-line pl-5">
              {events.map((e) => (
                <li key={e.event_id} className="relative animate-fade-in">
                  <span
                    className={`absolute -left-[26px] top-3 h-2.5 w-2.5 rounded-full ring-4 ring-surface ${
                      ["BLOCKED", "FAILED", "DENIED"].includes(e.status)
                        ? "bg-danger"
                        : ["PENDING", "IGNORED"].includes(e.status)
                          ? "bg-warn"
                          : "bg-ok"
                    }`}
                  />
                  <details className="group rounded-lg border border-line p-2.5 transition-colors hover:bg-raised/40">
                    <summary className="cursor-pointer list-none">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-2xs text-subtle">
                          {formatTime(e.timestamp)}
                        </span>
                        <Pill tone={AGENT_TONE[e.agent_id] ?? "mute"}>{e.agent_id}</Pill>
                        <code className="font-mono text-2xs font-semibold text-strong">
                          {e.action}
                        </code>
                        {e.status !== "OK" && <Pill tone={statusTone(e.status)}>{e.status}</Pill>}
                        <span className="ml-auto text-2xs text-subtle transition-transform group-open:rotate-90">
                          ▸
                        </span>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-body">{e.reason}</p>
                    </summary>

                    {(e.input_reference || e.output_reference || e.policy_result) && (
                      <div className="mt-2.5 space-y-2">
                        {e.policy_result && <Detail label="policy_result" data={e.policy_result} />}
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
      <pre className="mt-1 max-h-48 overflow-auto rounded-lg border border-line bg-raised p-2 font-mono text-[10px] leading-relaxed text-subtle">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
