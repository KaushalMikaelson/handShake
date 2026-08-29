import { useEffect, useState } from "react";
import { api, type BuyerState, type ShopResponse } from "../services/api";
import { formatINR } from "../services/format";
import { Card, Empty, ErrorBanner, Meter, Pill, statusTone } from "../components/ui";
import { PolicyReport } from "../components/PolicyReport";

/** Scripted prompts (PRD 5.7 Q4) so each demo beat triggers reliably. */
const SCRIPTS = [
  {
    label: "Auto-purchase (under ₹2,000)",
    query: "Buy me a braided aux cable for my headphones, budget Rs 1000",
    hint: "Level 3 autonomy: passes policy, below the auto-purchase threshold, pays without asking.",
  },
  {
    label: "Approval gate (₹8,999)",
    query: "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony",
    hint: "Above the ₹5,000 approval threshold, so it routes to a human.",
  },
  {
    label: "Blocked (over limit)",
    query: "Buy premium Sennheiser wireless headphones, budget up to Rs 20,000",
    hint: "₹11,999 exceeds the ₹10,000 per-transaction cap. Razorpay is never called.",
  },
  {
    label: "Needs clarification",
    query: "Buy me some good headphones",
    hint: "No budget stated — the agent asks instead of assuming one.",
  },
];

const AUTONOMY = [
  { value: "L1_RECOMMEND", label: "L1 · Recommend only" },
  { value: "L2_PREPARE", label: "L2 · Always ask me" },
  { value: "L3_BOUNDED_AUTO", label: "L3 · Bounded auto-purchase" },
];

export default function BuyerPage() {
  const [state, setState] = useState<BuyerState | null>(null);
  const [query, setQuery] = useState(SCRIPTS[0].query);
  const [result, setResult] = useState<ShopResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acceptBundle, setAcceptBundle] = useState(false);

  const refresh = () => api.buyerState().then(setState).catch(() => {});
  useEffect(() => { refresh(); }, []);

  async function run(q: string) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.shop(q, { acceptBundle }));
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function setAutonomy(level: string) {
    try {
      await api.updatePolicy({ autonomy_level: level });
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      {/* ---------------- left: agent state + policy ---------------- */}
      <div className="space-y-4">
        <Card title="Agent status" subtitle={state ? `Acting for ${state.name}` : "Loading…"}>
          {state && (
            <div className="space-y-3">
              <div>
                <span className="label">Autonomy level</span>
                <div className="mt-1 space-y-1">
                  {AUTONOMY.map((a) => (
                    <button
                      key={a.value}
                      onClick={() => setAutonomy(a.value)}
                      className={`w-full rounded-md border px-2 py-1.5 text-left text-xs transition ${
                        state.policy.autonomy_level === a.value
                          ? "border-accent bg-accent/15 text-slate-100"
                          : "border-edge text-muted hover:bg-edge/40"
                      }`}
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
              </div>

              <Meter used={state.spent_today} total={state.policy.daily_budget} label="Daily budget" />
              <p className="text-[11px] text-muted">
                {formatINR(state.spent_today)} spent · {formatINR(state.remaining_today)} left today
              </p>

              <Meter
                used={state.spent_this_month}
                total={state.policy.monthly_budget}
                label="Monthly budget"
              />
              <p className="text-[11px] text-muted">
                {formatINR(state.spent_this_month)} spent ·{" "}
                {formatINR(state.remaining_this_month)} left this month
              </p>
            </div>
          )}
        </Card>

        <Card title="Active policy" subtitle="Hard limits the agent cannot exceed">
          {state && (
            <dl className="space-y-1.5 text-xs">
              <Row k="Max per transaction" v={formatINR(state.policy.max_transaction)} />
              <Row k="Ask above" v={formatINR(state.policy.require_approval_above)} />
              <Row k="Auto-buy below" v={formatINR(state.policy.allow_automatic_purchase_below)} />
              <Row k="Allowed" v={state.policy.allowed_categories.join(", ")} />
              <Row k="Blocked" v={state.policy.blocked_categories.join(", ") || "—"} />
            </dl>
          )}
        </Card>

        <Card title="Agent permissions" subtitle="Fixed capability set — the LLM cannot extend it">
          {state && (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-1">
                {state.permissions_allowed.map((p) => (
                  <Pill key={p} tone="pass">{p}</Pill>
                ))}
              </div>
              <div className="flex flex-wrap gap-1">
                {state.permissions_denied.map((p) => (
                  <Pill key={p} tone="fail">✕ {p}</Pill>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* ---------------- right: shopping flow ---------------- */}
      <div className="space-y-4">
        <Card title="Shopping request" subtitle="Describe the goal in plain language">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={2}
            className="w-full resize-none rounded-md border border-edge bg-ink p-2.5 text-sm text-slate-200 outline-none focus:border-accent"
            placeholder="Buy me wireless headphones under ₹10,000, prefer Sony…"
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button className="btn-primary" disabled={loading || !query.trim()} onClick={() => run(query)}>
              {loading ? "Agent working…" : "Run buyer agent"}
            </button>
            <label className="flex items-center gap-1.5 text-xs text-muted">
              <input
                type="checkbox"
                checked={acceptBundle}
                onChange={(e) => setAcceptBundle(e.target.checked)}
                className="accent-[#5b8cff]"
              />
              accept bundle if offered
            </label>
          </div>

          <div className="mt-3 border-t border-edge pt-3">
            <span className="label">Scripted demo prompts</span>
            <div className="mt-1.5 grid gap-1.5 sm:grid-cols-2">
              {SCRIPTS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => { setQuery(s.query); run(s.query); }}
                  disabled={loading}
                  className="rounded-md border border-edge p-2 text-left transition hover:border-accent/60 hover:bg-edge/30 disabled:opacity-50"
                >
                  <span className="block text-xs font-medium text-slate-200">{s.label}</span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-muted">{s.hint}</span>
                </button>
              ))}
            </div>
          </div>
        </Card>

        <ErrorBanner error={error} />
        {result ? <ShopResult result={result} onChanged={refresh} /> : !loading && (
          <Card><Empty>Run the agent to see its decision, the policy verdict, and the audit trail.</Empty></Card>
        )}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted">{k}</dt>
      <dd className="text-right text-slate-300">{v}</dd>
    </div>
  );
}

function ShopResult({ result, onChanged }: { result: ShopResponse; onChanged: () => void }) {
  const [deciding, setDeciding] = useState(false);
  const [decided, setDecided] = useState<ShopResponse | null>(null);

  async function decide(d: "approve" | "reject") {
    if (!result.approval) return;
    setDeciding(true);
    try {
      setDecided(await api.decide(result.approval.approval_id, d));
      onChanged();
    } finally {
      setDeciding(false);
    }
  }

  const final = decided ?? result;

  return (
    <div className="space-y-4">
      <Card
        title="Outcome"
        right={<Pill tone={statusTone(final.status)}>{final.status}</Pill>}
      >
        <p className="text-sm text-slate-200">{final.message}</p>
        {!final.razorpay_called && (
          <p className="mt-2 rounded border border-edge bg-ink/60 p-2 text-[11px] text-muted">
            Razorpay was <strong className="text-slate-300">not called</strong> on this path.
          </p>
        )}
      </Card>

      {result.needs_clarification && (
        <Card title="Agent needs clarification">
          <p className="text-sm text-warn">{result.clarification_question}</p>
          <p className="mt-2 text-[11px] text-muted">
            The agent will not assume a budget you did not state.
          </p>
        </Card>
      )}

      {result.recommendation && (
        <Card
          title="Agent recommendation"
          subtitle={`ranked via ${result.recommendation.llm_mode} path`}
        >
          {result.recommendation.selected_name && (
            <div className="mb-3 rounded-md border border-accent/30 bg-accent/5 p-3">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-100">
                  {result.recommendation.selected_name}
                </h3>
                <span className="font-mono text-sm text-slate-100">
                  {formatINR(result.recommendation.amount)}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-slate-300">
                {result.recommendation.justification}
              </p>
              {result.recommendation.remaining_budget !== null && (
                <p className="mt-1 text-[11px] text-muted">
                  Remaining budget: {formatINR(result.recommendation.remaining_budget)}
                </p>
              )}
            </div>
          )}

          <span className="label">Every candidate considered</span>
          <ul className="mt-1.5 space-y-1">
            {result.recommendation.candidates.map((c) => (
              <li
                key={c.product_id}
                className="flex items-start gap-2 rounded border border-edge/60 p-2 text-xs"
              >
                <span className={c.eligible ? "text-pass" : "text-fail"}>
                  {c.eligible ? "✓" : "✕"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-2">
                    <span className="truncate text-slate-200">{c.name}</span>
                    <span className="font-mono text-muted">{formatINR(c.price)}</span>
                  </div>
                  <p className="text-[11px] text-muted">
                    {c.eligible ? c.reasons.join(" · ") : c.rejection_reason}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {result.bundle && (
        <Card
          title="Merchant growth agent"
          right={<Pill tone={result.bundle.offered ? "info" : "mute"}>
            {result.bundle.offered ? `bundle · ${result.bundle.discount_pct}% off` : "no_bundle_offered"}
          </Pill>}
        >
          <p className="text-xs leading-relaxed text-slate-300">{result.bundle.reasoning}</p>
          {result.bundle.offered && (
            <div className="mt-2 flex items-baseline gap-3 text-xs">
              <span className="text-muted line-through">{formatINR(result.bundle.list_price)}</span>
              <span className="font-mono text-sm text-pass">{formatINR(result.bundle.bundle_price)}</span>
            </div>
          )}
        </Card>
      )}

      {result.policy && (
        <Card title="Policy engine verdict" subtitle="Deterministic — no LLM in this path">
          <PolicyReport policy={result.policy} />
        </Card>
      )}

      {result.approval && result.approval.status === "PENDING" && !decided && (
        <Card title="Human approval required" subtitle="Above your approval threshold">
          <div className="mb-3 space-y-1 text-xs">
            <Row k="Amount" v={formatINR(result.approval.amount)} />
            <Row
              k="Remaining after purchase"
              v={formatINR(result.approval.context?.remaining_after_purchase)}
            />
            <Row k="Merchant" v={result.approval.context?.merchant?.name ?? "—"} />
          </div>
          <div className="flex gap-2">
            <button className="btn-primary" disabled={deciding} onClick={() => decide("approve")}>
              Approve
            </button>
            <button className="btn-danger" disabled={deciding} onClick={() => decide("reject")}>
              Reject
            </button>
          </div>
        </Card>
      )}

      {final.transaction && (
        <Card title="Transaction" right={<Pill tone={statusTone(final.transaction.status)}>
          {final.transaction.status}
        </Pill>}>
          <dl className="space-y-1 text-xs">
            <Row k="Amount" v={formatINR(final.transaction.amount)} />
            <Row k="Razorpay order" v={final.transaction.razorpay_order_id ?? "—"} />
            <Row k="Payment id" v={final.transaction.razorpay_payment_id ?? "—"} />
            <Row k="Idempotency key" v={final.transaction.idempotency_key} />
          </dl>
        </Card>
      )}

      {result.trust && (
        <Card
          title="Merchant trust"
          right={<Pill tone={result.trust.score >= 85 ? "pass" : "warn"}>
            {result.trust.score}/100 · {result.trust.band}
          </Pill>}
        >
          <ul className="space-y-1">
            {result.trust.signals.map((s) => (
              <li key={s.name} className="flex items-start gap-2 text-xs">
                <span className={s.passed ? "text-pass" : "text-fail"}>{s.passed ? "✓" : "✕"}</span>
                <div>
                  <code className="font-mono text-[11px] text-slate-400">{s.name}</code>
                  <p className="text-[11px] text-muted">{s.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-2 rounded border border-edge bg-ink/60 p-2 text-[11px] text-muted">
            {result.trust.advisory_note}
          </p>
        </Card>
      )}

      {final.intent && (
        <p className="text-[11px] text-muted">
          Purchase intent <code className="font-mono text-slate-400">{final.intent.intent_id}</code> —
          open the Audit Trail tab for its full timeline.
        </p>
      )}
    </div>
  );
}
