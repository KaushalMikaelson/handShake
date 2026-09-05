import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type BuyerState, type Product, type ShopResponse } from "../services/api";
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

/** Scripted prompts to test key agent behaviors and demo beats. */
const SCRIPTS = [
  {
    label: "Auto-purchase with Bundle",
    badge: "under ₹5,000",
    query: "Buy me boAt Rockerz 551ANC wireless headphones, budget Rs 4500",
    hint: "Within auto-buy threshold — agent automatically pairs Hardshell Case bundle and executes.",
    tagColor: "bg-ok/15 text-ok border-ok/30",
  },
  {
    label: "Approval Gate with Bundle",
    badge: "₹29,990",
    query: "Buy me Sony WH-1000XM5 premium noise cancelling headphones, budget Rs 35,000",
    hint: "Above ₹10,000 approval limit — agent proposes companion stand bundle & requests human sign-off.",
    tagColor: "bg-warn/15 text-warn border-warn/30",
  },
  {
    label: "Blocked by Policy",
    badge: "over limit",
    query: "Buy ASUS ROG Zephyrus G14 OLED Gaming Laptop, budget up to Rs 2,50,000",
    hint: "Exceeds ₹2,00,000 max transaction cap — Razorpay zero-called and blocked safely.",
    tagColor: "bg-danger/15 text-danger border-danger/30",
  },
  {
    label: "Needs Clarification",
    badge: "no budget",
    query: "Buy me some good headphones",
    hint: "No budget stated — agent halts and asks for budget clarification instead of guessing.",
    tagColor: "bg-brand/15 text-brand border-brand/30",
  },
];

const AUTONOMY = [
  { value: "L1_RECOMMEND", label: "Recommend only", detail: "Suggest, never buy" },
  { value: "L2_PREPARE", label: "Always ask me", detail: "Approve every purchase" },
  { value: "L3_BOUNDED_AUTO", label: "Bounded auto-buy", detail: "Buy small amounts alone" },
];

const CATEGORIES = [
  { id: "all", label: "All Items" },
  { id: "electronics", label: "🎧 Audio & Video" },
  { id: "computing", label: "💻 Laptops & Peripherals" },
  { id: "gaming", label: "🎮 Gaming Gear" },
  { id: "wearables", label: "⌚ Wearables" },
  { id: "smart_home", label: "🏠 Smart Home" },
];

function mergeShopResponse(previous: ShopResponse | null, next: ShopResponse): ShopResponse {
  if (!previous) return next;
  return {
    ...previous,
    ...next,
    clarification_question: next.clarification_question ?? previous.clarification_question,
    parsed_intent: next.parsed_intent ?? previous.parsed_intent,
    recommendation: next.recommendation ?? previous.recommendation,
    bundle: next.bundle ?? previous.bundle,
    trust: next.trust ?? previous.trust,
    policy: next.policy ?? previous.policy,
    intent: next.intent ?? previous.intent,
    approval: next.approval ?? previous.approval,
    transaction: next.transaction ?? previous.transaction,
    razorpay_key_id: next.razorpay_key_id ?? previous.razorpay_key_id,
  };
}

function openRazorpayCheckout({
  shopResponse,
  onSuccess,
  onFailure,
  autoCompleteAfterMs = 2500,
}: {
  shopResponse: ShopResponse;
  onSuccess: (finalResponse: ShopResponse) => void;
  onFailure: (err: string) => void;
  autoCompleteAfterMs?: number;
}) {
  const txn = shopResponse.transaction;
  const key = shopResponse.razorpay_key_id;
  if (!txn || !txn.razorpay_order_id || !key) {
    onFailure("Missing Razorpay order or key information.");
    return;
  }

  let completed = false;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let autoCompleteTimer: ReturnType<typeof setTimeout> | null = null;

  const cleanup = () => {
    if (pollTimer) clearInterval(pollTimer);
    if (autoCompleteTimer) clearTimeout(autoCompleteTimer);
  };

  const handleSuccess = (finalResponse: ShopResponse) => {
    if (completed) return;
    completed = true;
    cleanup();
    onSuccess(finalResponse);
  };

  // 1. Webhook polling: every 1.2s check if webhook or server completed the transaction
  pollTimer = setInterval(async () => {
    try {
      const res = await api.transactionStatus(txn.id);
      if (res.status === "CAPTURED") {
        const full = await api.simulateTestPayment(txn.id);
        handleSuccess(full);
      }
    } catch {
      // ignore transient errors
    }
  }, 1200);

  // 2. Auto-complete in test mode: automatically simulate success after delay so payment succeeds on its own
  if (autoCompleteAfterMs > 0) {
    autoCompleteTimer = setTimeout(async () => {
      try {
        const full = await api.simulateTestPayment(txn.id);
        handleSuccess(full);
      } catch (err) {
        console.error("Auto test payment error:", err);
      }
    }, autoCompleteAfterMs);
  }

  if (typeof (window as any).Razorpay !== "undefined") {
    const options = {
      key: key,
      amount: txn.amount,
      currency: txn.currency || "INR",
      name: "Bounded AI Commerce",
      description: shopResponse.recommendation?.selected_name || "Autonomous Agent Purchase",
      order_id: txn.razorpay_order_id,
      handler: async function (response: {
        razorpay_payment_id: string;
        razorpay_order_id: string;
        razorpay_signature: string;
      }) {
        try {
          const verified = await api.verifyPayment({
            transaction_id: txn.id,
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          });
          handleSuccess(verified);
        } catch (err) {
          onFailure(err instanceof ApiError ? err.message : String(err));
        }
      },
      prefill: {
        name: "Aditi Sharma",
        email: "aditi@example.com",
        contact: "9876543210",
      },
      theme: {
        color: "#6366f1",
      },
      modal: {
        ondismiss: function () {
          console.log("Razorpay Checkout modal dismissed");
          cleanup();
        },
      },
    };

    const rzp = new (window as any).Razorpay(options);
    rzp.on("payment.failed", function (response: any) {
      cleanup();
      onFailure(response?.error?.description || "Payment failed at checkout");
    });
    rzp.open();
  }
}

export default function BuyerPage({ onChanged }: { onChanged?: () => void }) {
  const toast = useToast();
  const [state, setState] = useState<BuyerState | null>(null);
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [query, setQuery] = useState(SCRIPTS[0].query);
  const [result, setResult] = useState<ShopResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acceptBundle, setAcceptBundle] = useState(true);

  // Search selector state
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [selectedCat, setSelectedCat] = useState("all");
  const selectorRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(
    () => api.buyerState().then(setState).catch(() => undefined),
    [],
  );

  useEffect(() => {
    refresh();
    api.catalog().then((res) => setCatalog(res.products || [])).catch(() => undefined);
  }, [refresh]);

  // Click outside to close selector dropdown
  useEffect(() => {
    if (!selectorOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setSelectorOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [selectorOpen]);

  const filteredProducts = useMemo(() => {
    return catalog.filter((p) => {
      const matchCat =
        selectedCat === "all" ||
        p.category === selectedCat ||
        (selectedCat === "electronics" && (p.category === "electronics" || p.attributes.includes("wireless")));
      const q = searchFilter.toLowerCase().trim();
      if (!q) return matchCat;
      const matchText =
        p.name.toLowerCase().includes(q) ||
        p.brand.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q) ||
        p.attributes.some((a) => a.toLowerCase().includes(q));
      return matchCat && matchText;
    });
  }, [catalog, selectedCat, searchFilter]);

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

        if (r.status === "blocked") {
          toast.error("Purchase blocked", r.policy?.reason);
        } else if (r.status === "order_created" && r.razorpay_key_id) {
          toast.info("Razorpay Order Created", "Opening Checkout modal…");
          openRazorpayCheckout({
            shopResponse: r,
            onSuccess: async (finalResponse) => {
              setResult((prev) => mergeShopResponse(prev, finalResponse));
              await refresh();
              onChanged?.();
              toast.success("Payment captured", finalResponse.message);
            },
            onFailure: (errMsg) => {
              toast.error("Checkout incomplete", errMsg);
            },
          });
        } else if (r.status === "completed") {
          toast.success("Payment captured", r.message);
        } else if (r.status === "awaiting_approval") {
          toast.info("Approval needed", r.message);
        } else if (r.status === "needs_clarification") {
          toast.info("Agent needs a budget");
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [acceptBundle, refresh, onChanged, toast],
  );

  function selectProduct(p: Product, autoRun = false) {
    const rawPriceRupees = Math.round(p.price / 100);
    // Provide a budget that comfortably covers the product + potential companion bundle
    const headroomMultiplier = p.companion_product_ids && p.companion_product_ids.length > 0 ? 1.3 : 1.15;
    const budgetRupees = Math.ceil((rawPriceRupees * headroomMultiplier) / 100) * 100;
    const promptText = `Buy me ${p.name}, budget Rs ${budgetRupees.toLocaleString("en-IN")}`;
    setQuery(promptText);
    setSelectorOpen(false);
    toast.info("Product Selected", `Loaded prompt for ${p.name}`);
    if (autoRun) {
      run(promptText);
    }
  }

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
    <div className="grid gap-6 lg:grid-cols-[20rem_1fr] xl:grid-cols-[22rem_1fr] items-start">
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
        <Card
          title="Shopping request"
          subtitle="Describe what you want to buy in natural language, or choose from the 60+ item catalog"
          right={
            catalog.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-brand/10 border border-brand/20 px-2.5 py-1 text-2xs font-bold text-brand">
                <span>📦</span> {catalog.length} Products in Catalog
              </span>
            )
          }
        >
          {/* Inventory Quick-Pick Selector */}
          <div ref={selectorRef} className="relative mb-3">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <button
                type="button"
                onClick={() => setSelectorOpen((o) => !o)}
                className="inline-flex items-center gap-2 rounded-lg border border-brand/40 bg-brand/5 px-3 py-1.5 text-xs font-bold text-brand transition hover:bg-brand/10 hover:border-brand"
              >
                <span>🔍</span>
                <span>{selectorOpen ? "Close Product Selector" : "Browse & Pick from 60+ Products…"}</span>
                <span className="text-2xs">{selectorOpen ? "▴" : "▾"}</span>
              </button>

              <span className="text-2xs text-subtle font-medium hidden sm:inline">
                🎁 Companion bonus bundles auto-attach when available
              </span>
            </div>

            {selectorOpen && (
              <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-96 overflow-hidden rounded-xl border border-line bg-surface shadow-xl flex flex-col animate-fade-in">
                {/* Search & Category Filter Toolbar */}
                <div className="border-b border-line p-3 bg-raised/50 space-y-2">
                  <div className="relative">
                    <input
                      type="text"
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      placeholder="Filter 60+ products by name, brand, or feature (e.g. Sony, MacBook, Gaming, ANC)…"
                      className="input pl-8 text-xs h-9"
                      autoFocus
                    />
                    <span className="absolute left-2.5 top-2.5 text-subtle text-xs">🔍</span>
                    {searchFilter && (
                      <button
                        onClick={() => setSearchFilter("")}
                        className="absolute right-2.5 top-2 text-xs text-subtle hover:text-strong"
                      >
                        ✕
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-2xs scrollbar-none">
                    {CATEGORIES.map((cat) => (
                      <button
                        key={cat.id}
                        onClick={() => setSelectedCat(cat.id)}
                        className={`whitespace-nowrap rounded-lg px-2.5 py-1 font-semibold transition ${
                          selectedCat === cat.id
                            ? "bg-brand text-white shadow-xs"
                            : "bg-surface text-body hover:bg-raised border border-line"
                        }`}
                      >
                        {cat.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Product List */}
                <div className="overflow-y-auto max-h-64 p-2 space-y-1.5 divide-y divide-line/30">
                  {filteredProducts.length === 0 ? (
                    <div className="py-8 text-center text-xs text-subtle font-medium">
                      No products found matching "{searchFilter}".
                    </div>
                  ) : (
                    filteredProducts.map((p) => {
                      const hasCompanions = p.companion_product_ids && p.companion_product_ids.length > 0;
                      return (
                        <div
                          key={p.product_id}
                          className="group flex flex-wrap items-center justify-between gap-3 rounded-xl p-2.5 pt-3 transition hover:bg-raised/80"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-xs text-strong group-hover:text-brand transition">
                                {p.name}
                              </span>
                              <span className="rounded bg-surface border border-line px-1.5 py-0.5 text-3xs font-semibold text-subtle uppercase">
                                {p.brand}
                              </span>
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-2xs">
                              <span className="font-mono font-bold text-brand">{formatINR(p.price)}</span>
                              <span className="text-subtle">·</span>
                              <span className="text-subtle capitalize">{p.category}</span>
                              {hasCompanions && (
                                <span className="inline-flex items-center gap-1 rounded bg-ok/10 border border-ok/25 px-1.5 py-0.5 text-3xs font-bold text-ok">
                                  🎁 {p.companion_product_ids?.length} Bonus Pairings
                                </span>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => selectProduct(p, false)}
                            >
                              Load Prompt
                            </Button>
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => selectProduct(p, true)}
                            >
                              Shop Now
                            </Button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>

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
            <span className="label block mb-2.5">Scripted Demo Prompts (Click to test beats)</span>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {SCRIPTS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => {
                    setQuery(s.query);
                    run(s.query);
                  }}
                  disabled={loading}
                  className="group relative flex flex-col justify-between rounded-xl border border-line bg-surface p-3 text-left transition-all
                             hover:border-brand/50 hover:bg-brand/5 hover:shadow-xs disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5 w-full">
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
              Run the agent or pick a product from the 60+ catalog items above to test candidate evaluation, companion bundling discounts, and policy engine verification.
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
      if (d === "approve" && r.status === "order_created" && r.razorpay_key_id) {
        setDecided(mergeShopResponse(result, r));
        toast.info("Razorpay Order Created", "Opening Checkout modal…");
        openRazorpayCheckout({
          shopResponse: r,
          onSuccess: async (finalResponse) => {
            setDecided((prev) => mergeShopResponse(prev ?? result, finalResponse));
            onDecided();
            toast.success("Payment captured", finalResponse.message);
          },
          onFailure: (errMsg) => {
            toast.error("Checkout incomplete", errMsg);
          },
        });
      } else {
        setDecided(mergeShopResponse(result, r));
        onDecided();
        if (d === "approve") toast.success("Approved", r.message);
        else toast.info("Rejected", "No payment was attempted.");
      }
    } catch (e) {
      toast.error("Could not record decision", e instanceof ApiError ? e.message : undefined);
    } finally {
      setDeciding(null);
      setConfirmReject(false);
    }
  }

  const final = decided ?? result;
  const rec = final.recommendation;

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
        {final.status === "order_created" && final.razorpay_key_id && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand/30 bg-brand/10 p-3.5">
            <div>
              <p className="text-xs font-bold text-brand">⚡ Razorpay Checkout Ready (Test Mode)</p>
              <p className="text-2xs text-subtle font-medium">Auto-capturing test payment & listening for webhook…</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={async () => {
                  if (final.transaction?.id) {
                    try {
                      const res = await api.simulateTestPayment(final.transaction.id);
                      setDecided((prev) => mergeShopResponse(prev ?? result, res));
                      onDecided();
                      toast.success("Payment captured", res.message);
                    } catch {
                      toast.error("Failed to auto-complete test payment");
                    }
                  }
                }}
              >
                ⚡ Auto-Complete Test Payment
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  openRazorpayCheckout({
                    shopResponse: final,
                    onSuccess: async (finalResponse) => {
                      setDecided((prev) => mergeShopResponse(prev ?? result, finalResponse));
                      onDecided();
                      toast.success("Payment captured", finalResponse.message);
                    },
                    onFailure: (errMsg) => {
                      toast.error("Checkout incomplete", errMsg);
                    },
                  });
                }}
              >
                💳 Re-open Modal
              </Button>
            </div>
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
      {final.bundle && (
        <Card
          title="Merchant Growth Agent"
          right={
            <Pill tone={final.bundle.offered ? "brand" : "mute"}>
              {final.bundle.offered
                ? `Bundle Offer · ${final.bundle.discount_pct}% OFF`
                : "No Bundle Offered"}
            </Pill>
          }
        >
          <p className="text-xs font-medium leading-relaxed text-body">{final.bundle.reasoning}</p>
          {final.bundle.offered && (
            <div className="mt-3 flex items-center gap-3 rounded-xl border border-ok/30 bg-ok/10 p-3">
              <span className="text-2xs font-bold text-subtle uppercase">Bundle Savings:</span>
              <span className="font-mono text-xs text-subtle line-through">
                {formatINR(final.bundle.list_price)}
              </span>
              <span className="font-mono text-sm font-bold text-ok">
                {formatINR(final.bundle.bundle_price)}
              </span>
            </div>
          )}
        </Card>
      )}

      {/* Policy Engine Verdict */}
      {final.policy && (
        <Card title="Policy Engine Verdict" subtitle="Deterministic Evaluation — Zero LLM / Zero Network">
          <PolicyReport policy={final.policy} />
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
      {final.trust && (
        <Card
          title="Merchant Trust Score (Advisory Only)"
          right={
            <Pill tone={final.trust.score >= 85 ? "ok" : "warn"}>
              {final.trust.score}/100 · {final.trust.band}
            </Pill>
          }
        >
          <ul className="space-y-2">
            {final.trust.signals.map((s) => (
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
            {final.trust.advisory_note}
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
