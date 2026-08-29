import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type BuyerState, type ShopResponse } from "../services/api";
import { formatINR } from "../services/format";
import { useToast } from "../context/ToastContext";
import {
  Button,
  Card,
  Empty,
  ErrorBanner,
  Meter,
  Pill,
  Row,
  Skeleton,
  Tooltip,
  statusTone,
} from "../components/ui";
import { PolicyReport } from "../components/PolicyReport";

/** Scripted prompts so every demo beat triggers reliably (PRD 5.7 Q4). */
const SCRIPTS = [
  {
    label: "Auto-purchase",
    badge: "under ₹2,000",
    query: "Buy me a braided aux cable for my headphones, budget Rs 1000",
    hint: "Passes policy and sits below the auto-purchase threshold, so the agent pays without asking.",
  },
  {
    label: "Approval gate",
    badge: "₹8,999",
    query: "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony",
    hint: "Above your ₹5,000 approval threshold, so it routes to you.",
  },
  {
    label: "Blocked",
    badge: "over limit",
    query: "Buy premium Sennheiser wireless headphones, budget up to Rs 20,000",
    hint: "₹11,999 exceeds the ₹10,000 per-transaction cap. Razorpay is never called.",
  },
  {
    label: "Needs clarification",
    badge: "no budget",
    query: "Buy me some good headphones",
    hint: "No budget stated — the agent asks instead of assuming one.",
  },
];

const AUTONOMY = [
  { value: "L1_RECOMMEND", label: "Recommend only", detail: "Suggest, never buy" },
  { value: "L2_PREPARE", label: "Always ask me", detail: "Approve every purchase" },
  { value: "L3_BOUNDED_AUTO", label: "Bounded auto-buy", detail: "Buy small amounts alone" },
];

export default function BuyerPage({ onChanged }: { onChanged?: () => void }) {
  const toast = useToast();
  const [state, setState] = useState<BuyerState | null>(null);
  const [query, setQuery] = useState(SCRIPTS[0].query);
  const [result, setResult] = useState<ShopResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acceptBundle, setAcceptBundle] = useState(false);

  const refresh = useCallback(
    () => api.buyerState().then(setState).catch(() => undefined),
    [],
  );
  useEffect(() => {
    refresh();
  }, [refresh]);

  const run = useCallback(
    async (q: string) => {
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const r = await api.shop(q, { acceptBundle });
        setResult(r);
        await refresh();
        onChanged?.();

        if (r.status === "blocked") toast.error("Purchase blocked", r.policy?.reason);
        else if (r.status === "completed") toast.success("Payment captured", r.message);
        else if (r.status === "awaiting_approval") toast.info("Approval needed", r.message);
        else if (r.status === "needs_clarification") toast.info("Agent needs a budget");
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [acceptBundle, refresh, onChanged, toast],
  );

  async function setAutonomy(level: string) {
    try {
      await api.updatePolicy({ autonomy_level: level });
      await refresh();
      toast.success("Autonomy level updated");
    } catch (e) {
      toast.error("Could not update policy", e instanceof ApiError ? e.message : undefined);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[19rem_1fr]">
      {/* ---------------------------- left rail ---------------------------- */}
      <div className="space-y-4">
        <Card title="Agent status" subtitle={state ? `Acting for ${state.name}` : undefined}>
          {!state ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <span className="label">Autonomy level</span>
                <div className="mt-1.5 space-y-1">
                  {AUTONOMY.map((a) => {
                    const active = state.policy.autonomy_level === a.value;
                    return (
                      <button
                        key={a.value}
                        onClick={() => setAutonomy(a.value)}
                        aria-pressed={active}
                        className={`w-full rounded-lg border px-2.5 py-2 text-left transition-all ${
                          active
                            ? "border-brand bg-brand/10 ring-1 ring-inset ring-brand/25"
                            : "border-line hover:bg-raised"
                        }`}
                      >
                        <span
                          className={`block text-xs font-medium ${active ? "text-brand" : "text-body"}`}
                        >
                          {a.label}
                        </span>
                        <span className="block text-2xs text-subtle">{a.detail}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <Meter
                used={state.spent_today}
                total={state.policy.daily_budget}
                label="Daily budget"
                caption={
                  <>
                    {formatINR(state.spent_today)} spent ·{" "}
                    <strong className="text-body">{formatINR(state.remaining_today)}</strong> left
                  </>
                }
              />
              <Meter
                used={state.spent_this_month}
                total={state.policy.monthly_budget}
                label="Monthly budget"
                caption={
                  <>
                    {formatINR(state.spent_this_month)} spent ·{" "}
                    <strong className="text-body">{formatINR(state.remaining_this_month)}</strong>{" "}
                    left
                  </>
                }
              />
            </div>
          )}
        </Card>

        <Card title="Active policy" subtitle="Hard limits the agent cannot exceed">
          {state && (
            <dl className="divide-y divide-line">
              <Row k="Max per transaction" v={formatINR(state.policy.max_transaction)} mono />
              <Row k="Ask above" v={formatINR(state.policy.require_approval_above)} mono />
              <Row
                k="Auto-buy below"
                v={formatINR(state.policy.allow_automatic_purchase_below)}
                mono
              />
              <Row k="Allowed" v={state.policy.allowed_categories.join(", ")} />
              <Row k="Blocked" v={state.policy.blocked_categories.join(", ") || "—"} />
            </dl>
          )}
        </Card>

        <Card
          title="Agent permissions"
          subtitle="A fixed capability set the LLM cannot extend"
        >
          {state && (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-1">
                {state.permissions_allowed.map((p) => (
                  <Pill key={p} tone="ok">
                    {p}
                  </Pill>
                ))}
              </div>
              <div className="flex flex-wrap gap-1">
                {state.permissions_denied.map((p) => (
                  <Pill key={p} tone="danger">
                    ✕ {p}
                  </Pill>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* ---------------------------- main column ---------------------------- */}
      <div className="space-y-4">
        <Card title="Shopping request" subtitle="Describe the goal in plain language">
          <label htmlFor="shop-query" className="sr-only">
            Shopping request
          </label>
          <textarea
            id="shop-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && query.trim()) run(query);
            }}
            rows={2}
            className="input resize-none"
            placeholder="Buy me wireless headphones under ₹10,000, prefer Sony…"
          />
          <div className="mt-2.5 flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              loading={loading}
              disabled={!query.trim()}
              onClick={() => run(query)}
            >
              {loading ? "Agent working…" : "Run buyer agent"}
            </Button>
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-subtle">
              <input
                type="checkbox"
                checked={acceptBundle}
                onChange={(e) => setAcceptBundle(e.target.checked)}
                className="h-3.5 w-3.5 rounded accent-[rgb(var(--brand))]"
              />
              accept bundle if offered
            </label>
            <Tooltip label="Cmd/Ctrl + Enter">
              <span className="ml-auto hidden font-mono text-2xs text-subtle sm:inline">⌘↵</span>
            </Tooltip>
          </div>

          <div className="mt-4 border-t border-line pt-3">
            <span className="label">Scripted demo prompts</span>
            <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
              {SCRIPTS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => {
                    setQuery(s.query);
                    run(s.query);
                  }}
                  disabled={loading}
                  className="group rounded-lg border border-line p-2.5 text-left transition-all
                             hover:border-brand/50 hover:bg-brand/5 disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-strong">{s.label}</span>
                    <span className="font-mono text-2xs text-subtle">{s.badge}</span>
                  </div>
                  <p className="mt-0.5 text-2xs leading-snug text-subtle">{s.hint}</p>
                </button>
              ))}
            </div>
          </div>
        </Card>

        <ErrorBanner error={error} onRetry={() => run(query)} />

        {loading && <RunningSkeleton />}

        {!loading && result && (
          <ShopResult
            result={result}
            onDecided={async () => {
              await refresh();
              onChanged?.();
            }}
          />
        )}

        {!loading && !result && !error && (
          <Card>
            <Empty icon="◈" title="No run yet">
              Run the agent to see its decision, every candidate it considered, the per-rule
              policy verdict, and the audit trail it produced.
            </Empty>
          </Card>
        )}
      </div>
    </div>
  );
}

function RunningSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="card space-y-2.5 p-4">
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-3 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

function ShopResult({
  result,
  onDecided,
}: {
  result: ShopResponse;
  onDecided: () => void;
}) {
  const toast = useToast();
  const [deciding, setDeciding] = useState<"approve" | "reject" | null>(null);
  const [decided, setDecided] = useState<ShopResponse | null>(null);
  const [confirmReject, setConfirmReject] = useState(false);

  async function decide(d: "approve" | "reject") {
    if (!result.approval) return;
    setDeciding(d);
    try {
      const r = await api.decide(result.approval.approval_id, d);
      setDecided(r);
      onDecided();
      if (d === "approve") toast.success("Approved", r.message);
      else toast.info("Rejected", "No payment was attempted.");
    } catch (e) {
      toast.error("Could not record decision", e instanceof ApiError ? e.message : undefined);
    } finally {
      setDeciding(null);
      setConfirmReject(false);
    }
  }

  const final = decided ?? result;
  const rec = result.recommendation;

  return (
    <div className="animate-fade-up space-y-4">
      <Card title="Outcome" right={<Pill tone={statusTone(final.status)}>{final.status}</Pill>}>
        <p className="text-sm leading-relaxed text-body">{final.message}</p>
        {!final.razorpay_called && (
          <p className="mt-2.5 flex items-center gap-2 rounded-lg border border-line bg-raised/50 p-2.5 text-2xs text-subtle">
            <span className="text-ok">✓</span>
            Razorpay was <strong className="text-body">not called</strong> on this path.
          </p>
        )}
      </Card>

      {result.needs_clarification && (
        <Card title="Agent needs clarification">
          <p className="text-sm text-warn">{result.clarification_question}</p>
          <p className="mt-2 text-2xs text-subtle">
            The agent will not assume a budget you did not state.
          </p>
        </Card>
      )}

      {rec && (
        <Card title="Agent recommendation" subtitle={`ranked via the ${rec.llm_mode} path`}>
          {rec.selected_name && (
            <div className="mb-4 rounded-lg border border-brand/30 bg-brand/5 p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-sm font-semibold text-strong">{rec.selected_name}</h3>
                <span className="font-mono text-base font-semibold text-strong">
                  {formatINR(rec.amount)}
                </span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-body">{rec.justification}</p>
              {rec.remaining_budget !== null && (
                <p className="mt-1.5 text-2xs text-subtle">
                  Remaining budget: {formatINR(rec.remaining_budget)}
                </p>
              )}
            </div>
          )}

          <span className="label">Every candidate considered</span>
          <ul className="mt-2 space-y-1">
            {rec.candidates.map((c) => (
              <li
                key={c.product_id}
                className="flex items-start gap-2.5 rounded-lg border border-line p-2.5"
              >
                <span
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${
                    c.eligible ? "bg-ok/15 text-ok" : "bg-danger/15 text-danger"
                  }`}
                >
                  {c.eligible ? "✓" : "✕"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-2">
                    <span className="truncate text-xs text-strong">{c.name}</span>
                    <span className="shrink-0 font-mono text-xs text-subtle">
                      {formatINR(c.price)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-2xs text-subtle">
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
          right={
            <Pill tone={result.bundle.offered ? "brand" : "mute"}>
              {result.bundle.offered
                ? `bundle · ${result.bundle.discount_pct}% off`
                : "no_bundle_offered"}
            </Pill>
          }
        >
          <p className="text-xs leading-relaxed text-body">{result.bundle.reasoning}</p>
          {result.bundle.offered && (
            <div className="mt-2 flex items-baseline gap-3">
              <span className="font-mono text-xs text-subtle line-through">
                {formatINR(result.bundle.list_price)}
              </span>
              <span className="font-mono text-sm font-semibold text-ok">
                {formatINR(result.bundle.bundle_price)}
              </span>
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
        <Card title="Your approval is required" subtitle="This is above your approval threshold">
          <dl className="mb-3 divide-y divide-line">
            <Row k="Amount" v={formatINR(result.approval.amount)} mono />
            <Row
              k="Remaining after purchase"
              v={formatINR(result.approval.context?.remaining_after_purchase)}
              mono
            />
            <Row k="Merchant" v={result.approval.context?.merchant?.name ?? "—"} />
          </dl>

          {confirmReject ? (
            <div className="rounded-lg border border-danger/40 bg-danger/8 p-3">
              <p className="mb-2.5 text-xs text-body">
                Reject this purchase? The flow ends here and nothing is charged.
              </p>
              <div className="flex gap-2">
                <Button variant="danger" size="sm" loading={deciding === "reject"} onClick={() => decide("reject")}>
                  Yes, reject
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirmReject(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <Button variant="primary" loading={deciding === "approve"} onClick={() => decide("approve")}>
                Approve
              </Button>
              <Button variant="danger" onClick={() => setConfirmReject(true)}>
                Reject
              </Button>
            </div>
          )}
        </Card>
      )}

      {final.transaction && (
        <Card
          title="Transaction"
          right={<Pill tone={statusTone(final.transaction.status)}>{final.transaction.status}</Pill>}
        >
          <dl className="divide-y divide-line">
            <Row k="Amount" v={formatINR(final.transaction.amount)} mono />
            <Row k="Razorpay order" v={final.transaction.razorpay_order_id ?? "—"} mono />
            <Row k="Payment id" v={final.transaction.razorpay_payment_id ?? "—"} mono />
            <Row k="Idempotency key" v={final.transaction.idempotency_key} mono />
          </dl>
        </Card>
      )}

      {result.trust && (
        <Card
          title="Merchant trust"
          right={
            <Pill tone={result.trust.score >= 85 ? "ok" : "warn"}>
              {result.trust.score}/100 · {result.trust.band}
            </Pill>
          }
        >
          <ul className="space-y-1">
            {result.trust.signals.map((s) => (
              <li key={s.name} className="flex items-start gap-2.5 text-xs">
                <span className={s.passed ? "text-ok" : "text-danger"}>{s.passed ? "✓" : "✕"}</span>
                <div>
                  <code className="font-mono text-2xs text-subtle">{s.name}</code>
                  <p className="text-2xs text-subtle">{s.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-2.5 rounded-lg border border-line bg-raised/50 p-2.5 text-2xs text-subtle">
            {result.trust.advisory_note}
          </p>
        </Card>
      )}

      {final.intent && (
        <p className="text-2xs text-subtle">
          Purchase intent <code className="font-mono text-body">{final.intent.intent_id}</code> —
          open the Audit Trail for its full timeline.
        </p>
      )}
    </div>
  );
}
