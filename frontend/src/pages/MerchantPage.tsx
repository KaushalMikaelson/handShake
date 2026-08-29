import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Opportunity, type TrustReport } from "../services/api";
import { formatINR } from "../services/format";
import { useToast } from "../context/ToastContext";
import {
  Button,
  Card,
  Empty,
  ErrorBanner,
  Pill,
  Skeleton,
  Stat,
  statusTone,
} from "../components/ui";

/**
 * Merchant dashboard (US-5b).
 *
 * Opportunities come from declared catalog companion relationships, not a live
 * recommender. Only APPROVED ones are eligible for the growth agent to offer,
 * so a human gates every pairing before a buyer ever sees it.
 */
export default function MerchantPage() {
  const toast = useToast();
  const [opportunities, setOpportunities] = useState<Opportunity[] | null>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [trust, setTrust] = useState<TrustReport | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [o, m, t] = await Promise.all([
        api.opportunities(),
        api.merchantMetrics(),
        api.merchantTrust(),
      ]);
      setOpportunities(o);
      setMetrics(m);
      setTrust(t);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(id: string, d: "approve" | "reject") {
    setBusy(id);
    try {
      await api.decideOpportunity(id, d);
      await load();
      toast.success(d === "approve" ? "Opportunity approved" : "Opportunity rejected");
    } catch (e) {
      toast.error("Could not update opportunity", e instanceof ApiError ? e.message : undefined);
    } finally {
      setBusy(null);
    }
  }

  const approvedUplift = (opportunities ?? [])
    .filter((o) => o.status === "APPROVED")
    .reduce((sum, o) => sum + o.potential_aov_uplift, 0);

  return (
    <div className="space-y-4">
      <ErrorBanner error={error} onRetry={load} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics ? (
          <>
            <Stat label="Revenue" value={formatINR(metrics.revenue)} />
            <Stat label="Orders completed" value={String(metrics.orders_completed)} />
            <Stat label="Average order value" value={formatINR(metrics.average_order_value)} />
            <Stat
              label="Blocked by buyer policy"
              value={String(metrics.intents_blocked_by_policy)}
              hint="Purchases the buyer's own limits stopped"
            />
          </>
        ) : (
          [0, 1, 2, 3].map((i) => (
            <div key={i} className="card space-y-2 p-4">
              <Skeleton className="h-2.5 w-1/2" />
              <Skeleton className="h-6 w-3/4" />
            </div>
          ))
        )}
      </div>

      <Card
        title="AI-identified growth opportunities"
        subtitle="Derived from declared catalog relationships — you approve each pairing"
        right={<Pill tone="brand">+{formatINR(approvedUplift)} approved uplift</Pill>}
      >
        {opportunities === null ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : opportunities.length === 0 ? (
          <Empty icon="◭">No opportunities configured for this catalog.</Empty>
        ) : (
          <div className="space-y-2">
            {opportunities.map((o) => (
              <div
                key={o.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-line p-3 transition-colors hover:bg-raised/40"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium text-strong">
                      {o.anchor_name} <span className="text-subtle">→</span> {o.companion_name}
                    </span>
                    <Pill tone={statusTone(o.status)}>{o.status}</Pill>
                  </div>
                  <p className="mt-1 text-2xs leading-snug text-subtle">{o.rationale}</p>
                  <p className="mt-1 font-mono text-2xs text-ok">
                    +{formatINR(o.potential_aov_uplift)} potential AOV
                  </p>
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={busy === o.id}
                    disabled={o.status === "APPROVED"}
                    onClick={() => decide(o.id, "approve")}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    disabled={busy === o.id || o.status === "REJECTED"}
                    onClick={() => decide(o.id, "reject")}
                  >
                    Reject
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 rounded-lg border border-line bg-raised/50 p-2.5 text-2xs leading-relaxed text-subtle">
          Rejecting a pairing removes it from the growth agent's options immediately. The agent can
          only bundle what you have approved, and it never writes catalog pricing itself.
        </p>
      </Card>

      {trust && (
        <Card
          title="Merchant trust profile"
          subtitle="An advisory ranking signal only"
          right={
            <Pill tone={trust.score >= 85 ? "ok" : "warn"}>
              {trust.score}/100 · {trust.band}
            </Pill>
          }
        >
          <ul className="space-y-1">
            {trust.signals.map((s) => (
              <li
                key={s.name}
                className="flex items-start gap-2.5 rounded-lg border border-line p-2.5"
              >
                <span
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${
                    s.passed ? "bg-ok/15 text-ok" : "bg-danger/15 text-danger"
                  }`}
                >
                  {s.passed ? "✓" : "✕"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-2">
                    <code className="font-mono text-2xs text-subtle">{s.name}</code>
                    <span className="text-2xs text-subtle">weight {s.weight}</span>
                  </div>
                  <p className="mt-0.5 text-2xs text-subtle">{s.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-2.5 rounded-lg border border-line bg-raised/50 p-2.5 text-2xs text-subtle">
            {trust.advisory_note}
          </p>
        </Card>
      )}
    </div>
  );
}
