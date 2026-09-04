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
    hint: "Passes policy and sits below auto-purchase threshold — agent pays automatically.",
    tagColor: "bg-ok/15 text-ok border-ok/30",
  },
  {
    label: "Approval gate",
    badge: "₹8,999",
    query: "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony",
    hint: "Above ₹5,000 threshold — requires your explicit human approval.",
    tagColor: "bg-warn/15 text-warn border-warn/30",
  },
  {
    label: "Blocked by policy",
    badge: "over limit",
    query: "Buy premium Sennheiser wireless headphones, budget up to Rs 20,000",
    hint: "₹11,999 exceeds ₹10,000 max transaction cap — Razorpay zero-called.",
    tagColor: "bg-danger/15 text-danger border-danger/30",
  },
  {
    label: "Needs clarification",
    badge: "no budget",
    query: "Buy me some good headphones",
    hint: "No budget stated — agent asks instead of inventing one.",
    tagColor: "bg-brand/15 text-brand border-brand/30",
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
    <div className="grid gap-5 xl:grid-cols-[20rem_1fr]">
      {/* ---------------------------- left rail ---------------------------- */}
      <div className="space-y-5">
        <Card title="Agent status" subtitle={state ? `Acting for ${state.name}` : undefined}>
          {!state ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : (
            <div className="space-y-5">
              <div>
                <span className="label">Autonomy level</span>
                <div className="mt-2 space-y-1.5">
                  {AUTONOMY.map((a) => {
                    const active = state.policy.autonomy_level === a.value;
                    return (
                      <button
                        key={a.value}
                        onClick={() => setAutonomy(a.value)}
                        aria-pressed={active}
                        className={`w-full rounded-xl border p-3 text-left transition-all ${
                          active
                            ? "border-brand bg-brand/10 ring-2 ring-brand/30 shadow-xs"
                            : "border-line bg-surface hover:bg-raised hover:border-brand/40"
                        }`}
                      >
                        <span
                          className={`block text-xs font-bold ${active ? "text-brand" : "text-strong"}`}
                        >
                          {a.label}
                        </span>
                        <span className="block text-2xs text-subtle font-medium">{a.detail}</span>
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
                    <strong className="text-strong font-semibold">{formatINR(state.remaining_today)}</strong> left
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
                    <strong className="text-strong font-semibold">{formatINR(state.remaining_this_month)}</strong>{" "}
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
              <Row k="Allowed categories" v={state.policy.allowed_categories.join(", ")} />
              <Row k="Blocked categories" v={state.policy.blocked_categories.join(", ") || "—"} />
            </dl>
          )}
        </Card>

        <Card
          title="Agent permissions"
          subtitle="Fixed capability set the LLM cannot extend"
        >
          {state && (
            <div className="space-y-3">
              <div>
                <span className="label text-2xs mb-1.5 block">Granted Capabilities</span>
                <div className="flex flex-wrap gap-1.5">
                  {state.permissions_allowed.map((p) => (
                    <Pill key={p} tone="ok">
                      ✓ {p}
                    </Pill>
                  ))}
                </div>
              </div>
              <div>
                <span className="label text-2xs mb-1.5 block">Explicitly Denied</span>
                <div className="flex flex-wrap gap-1.5">
                  {state.permissions_denied.map((p) => (
                    <Pill key={p} tone="danger">
                      ✕ {p}
                    </Pill>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* ---------------------------- main column ---------------------------- */}
      <div className="space-y-5">
        <Card title="Shopping request" subtitle="Describe what you want to buy in natural language">
          <label htmlFor="shop-query" className="sr-only">
            Shopping request
          </label>
          <div className="relative">
            <textarea
              id="shop-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && query.trim()) run(query);
              }}
              rows={3}
              className="input resize-none text-sm font-medium leading-relaxed"
              placeholder="Buy me wireless headphones under ₹10,000, prefer Sony…"
            />
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                loading={loading}
                disabled={!query.trim()}
                onClick={() => run(query)}
              >
                {loading ? "Agent evaluating…" : "Run Buyer Agent"}
              </Button>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-body select-none">
                <input
                  type="checkbox"
                  checked={acceptBundle}
                  onChange={(e) => setAcceptBundle(e.target.checked)}
                  className="h-4 w-4 rounded border-line accent-brand focus:ring-brand/30"
                />
                Accept merchant bundle if offered
              </label>
            </div>

            <Tooltip label="Press Cmd/Ctrl + Enter to run">
              <span className="hidden font-mono text-2xs text-subtle bg-raised border border-line px-2 py-1 rounded-md sm:inline">⌘ + Enter</span>
            </Tooltip>
          </div>

          <div className="mt-5 border-t border-line pt-4">
            <span className="label block mb-2">Scripted Demo Prompts (Click to test beats)</span>
            <div className="grid gap-2 sm:grid-cols-2">
              {SCRIPTS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => {
                    setQuery(s.query);
                    run(s.query);
                  }}
                  disabled={loading}
                  className="group relative rounded-xl border border-line bg-surface p-3 text-left transition-all
                             hover:border-brand/50 hover:bg-brand/5 hover:shadow-xs disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs font-bold text-strong group-hover:text-brand">{s.label}</span>
                    <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 font-mono text-2xs font-bold ${s.tagColor}`}>
                      {s.badge}
                    </span>
                  </div>
                  <p className="text-2xs leading-relaxed text-subtle">{s.hint}</p>
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
            <Empty icon="◈" title="Ready to Shop">
              Run the agent to see product evaluation, candidate comparison, policy engine checks, and automated payment execution.
            </Empty>
          </Card>
        )}
      </div>
    </div>
  );
}

function RunningSkeleton() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((i) => (
        <div key={i} className="card space-y-3 p-5">
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
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
    <div className="animate-fade-up space-y-5">
      {/* Outcome Card */}
      <Card title="Transaction Outcome" right={<Pill tone={statusTone(final.status)}>{final.status}</Pill>}>
        <p className="text-sm font-medium leading-relaxed text-strong">{final.message}</p>
        {!final.razorpay_called && (
          <div className="mt-3 flex items-center gap-2 rounded-xl border border-ok/30 bg-ok/10 p-3 text-xs font-semibold text-ok">
            <span>🛡️</span>
            <span>Razorpay was <strong className="underline">zero-called</strong> on this path. Policy engine enforced safety before gateway invocation.</span>
          </div>
        )}
      </Card>

      {/* Clarification Needed */}
      {result.needs_clarification && (
        <Card title="Clarification Required">
          <div className="rounded-xl border border-warn/40 bg-warn/10 p-4">
            <p className="text-sm font-bold text-warn">{result.clarification_question}</p>
            <p className="mt-1 text-xs text-subtle font-medium">
              Safety Control: The agent will not guess or assume a budget you did not explicitly specify.
            </p>
          </div>
        </Card>
      )}

      {/* Agent Recommendation */}
      {rec && (
        <Card title="Agent Recommendation" subtitle={`Ranked & justified via ${rec.llm_mode.toUpperCase()} model path`}>
          {rec.selected_name && (
            <div className="mb-5 rounded-xl border border-brand/40 bg-gradient-to-r from-brand/15 via-brand/5 to-transparent p-4 shadow-xs">
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-brand/20 pb-2.5">
                <div>
                  <span className="label text-2xs text-brand block mb-0.5">Selected Winner</span>
                  <h3 className="text-base font-bold text-strong">{rec.selected_name}</h3>
                </div>
                <span className="font-mono text-lg font-bold text-brand">
                  {formatINR(rec.amount)}
                </span>
              </div>
              <p className="mt-2.5 text-xs font-medium leading-relaxed text-body">{rec.justification}</p>
              {rec.remaining_budget !== null && (
                <div className="mt-3 flex items-center justify-between text-2xs font-mono text-subtle bg-surface/60 border border-line px-3 py-1.5 rounded-lg">
                  <span>Remaining Budget After Purchase:</span>
                  <strong className="text-strong font-bold">{formatINR(rec.remaining_budget)}</strong>
                </div>
              )}
            </div>
          )}

          <span className="label block mb-2.5">Every Candidate Evaluated</span>
          <ul className="space-y-2">
            {rec.candidates.map((c) => {
              const isSelected = c.product_id === rec.selected_product_id;
              return (
                <li
                  key={c.product_id}
                  className={`flex items-start gap-3 rounded-xl border p-3 transition-all ${
                    isSelected
                      ? "border-brand bg-brand/5 ring-1 ring-brand/30"
                      : c.eligible
                      ? "border-line bg-surface"
                      : "border-line/60 bg-raised/30 opacity-75"
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-extrabold ${
                      c.eligible ? "bg-ok text-white" : "bg-danger text-white"
                    }`}
                  >
                    {c.eligible ? "✓" : "✕"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-bold text-strong">{c.name}</span>
                      <span className="shrink-0 font-mono text-xs font-bold text-strong">
                        {formatINR(c.price)}
                      </span>
                    </div>
                    <p className={`mt-1 text-2xs font-medium ${c.eligible ? "text-subtle" : "text-danger font-semibold"}`}>
                      {c.eligible ? c.reasons.join(" · ") : c.rejection_reason}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      {/* Merchant Growth Agent Bundle */}
      {result.bundle && (
        <Card
          title="Merchant Growth Agent"
          right={
            <Pill tone={result.bundle.offered ? "brand" : "mute"}>
              {result.bundle.offered
                ? `Bundle Offer · ${result.bundle.discount_pct}% OFF`
                : "No Bundle Offered"}
            </Pill>
          }
        >
          <p className="text-xs font-medium leading-relaxed text-body">{result.bundle.reasoning}</p>
          {result.bundle.offered && (
            <div className="mt-3 flex items-center gap-3 rounded-xl border border-ok/30 bg-ok/10 p-3">
              <span className="text-2xs font-bold text-subtle uppercase">Bundle Savings:</span>
              <span className="font-mono text-xs text-subtle line-through">
                {formatINR(result.bundle.list_price)}
              </span>
              <span className="font-mono text-sm font-bold text-ok">
                {formatINR(result.bundle.bundle_price)}
              </span>
            </div>
          )}
        </Card>
      )}

      {/* Policy Engine Verdict */}
      {result.policy && (
        <Card title="Policy Engine Verdict" subtitle="Deterministic Evaluation — Zero LLM / Zero Network">
          <PolicyReport policy={result.policy} />
        </Card>
      )}

      {/* Human Approval Gate */}
      {result.approval && result.approval.status === "PENDING" && !decided && (
        <Card title="Human Approval Required" subtitle="Transaction amount is at or above your approval threshold">
          <div className="rounded-xl border border-warn/40 bg-warn/10 p-4 mb-4">
            <dl className="divide-y divide-warn/20">
              <Row k="Total Purchase Amount" v={formatINR(result.approval.amount)} mono />
              <Row
                k="Remaining Budget After Approval"
                v={formatINR(result.approval.context?.remaining_after_purchase)}
                mono
              />
              <Row k="Merchant Name" v={result.approval.context?.merchant?.name ?? "—"} />
            </dl>
          </div>

          {confirmReject ? (
            <div className="rounded-xl border border-danger/40 bg-danger/10 p-4">
              <p className="mb-3 text-xs font-bold text-danger">
                Confirm Rejection? The transaction will be cancelled immediately and ₹0 charged.
              </p>
              <div className="flex gap-3">
                <Button variant="danger" size="sm" loading={deciding === "reject"} onClick={() => decide("reject")}>
                  Yes, Reject Purchase
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirmReject(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-3">
              <Button variant="primary" loading={deciding === "approve"} onClick={() => decide("approve")}>
                Approve & Execute Payment
              </Button>
              <Button variant="danger" onClick={() => setConfirmReject(true)}>
                Reject Purchase
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Transaction Record */}
      {final.transaction && (
        <Card
          title="Payment Transaction Record"
          right={<Pill tone={statusTone(final.transaction.status)}>{final.transaction.status}</Pill>}
        >
          <dl className="divide-y divide-line">
            <Row k="Amount Paid" v={formatINR(final.transaction.amount)} mono />
            <Row k="Razorpay Order ID" v={final.transaction.razorpay_order_id ?? "—"} mono />
            <Row k="Payment ID" v={final.transaction.razorpay_payment_id ?? "—"} mono />
            <Row k="Idempotency Key" v={final.transaction.idempotency_key} mono />
          </dl>
        </Card>
      )}

      {/* Merchant Trust */}
      {result.trust && (
        <Card
          title="Merchant Trust Score (Advisory Only)"
          right={
            <Pill tone={result.trust.score >= 85 ? "ok" : "warn"}>
              {result.trust.score}/100 · {result.trust.band}
            </Pill>
          }
        >
          <ul className="space-y-2">
            {result.trust.signals.map((s) => (
              <li key={s.name} className="flex items-start gap-2.5 text-xs font-medium">
                <span className={s.passed ? "text-ok font-bold" : "text-danger font-bold"}>{s.passed ? "✓" : "✕"}</span>
                <div>
                  <code className="font-mono text-2xs text-strong">{s.name}</code>
                  <p className="text-2xs text-subtle">{s.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-3 rounded-xl border border-line bg-raised/50 p-3 text-2xs text-subtle font-medium">
            {result.trust.advisory_note}
          </p>
        </Card>
      )}

      {final.intent && (
        <p className="text-2xs font-mono text-subtle text-right">
          Purchase Intent ID: <code className="font-bold text-strong">{final.intent.intent_id}</code>
        </p>
      )}
    </div>
  );
}
