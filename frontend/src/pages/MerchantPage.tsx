import { useEffect, useState } from "react";
import { api, type Opportunity, type TrustReport } from "../services/api";
import { formatINR } from "../services/format";
import { Card, Empty, ErrorBanner, Pill, statusTone } from "../components/ui";

/**
 * Merchant dashboard (US-5b).
 *
 * Opportunities are derived from declared catalog companion relationships, not
 * a live recommender. Only APPROVED ones are eligible for the growth agent to
 * offer, so a human gates every pairing before a buyer ever sees it.
 */
export default function MerchantPage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [trust, setTrust] = useState<TrustReport | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [o, m, t] = await Promise.all([
        api.opportunities(),
        api.merchantMetrics(),
        api.merchantTrust(),
      ]);
      setOpportunities(o);
      setMetrics(m);
      setTrust(t);
    } catch (e) {
      setError(String(e));
    }
  };
  useEffect(() => { load(); }, []);

  async function decide(id: string, d: "approve" | "reject") {
    setBusy(id);
    try {
      await api.decideOpportunity(id, d);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  const pendingUplift = opportunities
    .filter((o) => o.status === "APPROVED")
    .reduce((sum, o) => sum + o.potential_aov_uplift, 0);

  return (
    <div className="space-y-4">
      <ErrorBanner error={error} />

      {metrics && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Revenue" value={formatINR(metrics.revenue)} />
          <Stat label="Orders completed" value={String(metrics.orders_completed)} />
          <Stat label="Average order value" value={formatINR(metrics.average_order_value)} />
          <Stat
            label="Blocked by buyer policy"
            value={String(metrics.intents_blocked_by_policy)}
            hint="Purchases the buyer's own limits stopped"
          />
        </div>
      )}

      <Card
        title="AI-identified growth opportunities"
        subtitle="Derived from declared catalog relationships — the merchant approves each pairing"
        right={<Pill tone="info">+{formatINR(pendingUplift)} approved uplift</Pill>}
      >
        {opportunities.length === 0 ? (
          <Empty>No opportunities configured.</Empty>
        ) : (
          <div className="space-y-2">
            {opportunities.map((o) => (
              <div
                key={o.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-edge p-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium text-slate-200">
                      {o.anchor_name} <span className="text-muted">→</span> {o.companion_name}
                    </span>
                    <Pill tone={statusTone(o.status)}>{o.status}</Pill>
                  </div>
                  <p className="mt-1 text-[11px] leading-snug text-muted">{o.rationale}</p>
                  <p className="mt-1 text-[11px] text-pass">
                    Potential AOV uplift: {formatINR(o.potential_aov_uplift)}
                  </p>
                </div>
                <div className="flex gap-1.5">
                  <button
                    className="btn-ghost text-xs"
                    disabled={busy === o.id || o.status === "APPROVED"}
                    onClick={() => decide(o.id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    className="btn-danger text-xs"
                    disabled={busy === o.id || o.status === "REJECTED"}
                    onClick={() => decide(o.id, "reject")}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 rounded border border-edge bg-ink/60 p-2 text-[11px] text-muted">
          Rejecting a pairing removes it from the growth agent's options immediately — the agent can
          only bundle what the merchant has approved, and it never writes catalog pricing itself.
        </p>
      </Card>

      {trust && (
        <Card
          title="Merchant trust profile"
          subtitle="Advisory ranking signal only"
          right={<Pill tone={trust.score >= 85 ? "pass" : "warn"}>{trust.score}/100 · {trust.band}</Pill>}
        >
          <ul className="space-y-1">
            {trust.signals.map((s) => (
              <li key={s.name} className="flex items-start gap-2 rounded border border-edge/60 p-2 text-xs">
                <span className={s.passed ? "text-pass" : "text-fail"}>{s.passed ? "✓" : "✕"}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-2">
                    <code className="font-mono text-[11px] text-slate-400">{s.name}</code>
                    <span className="text-[11px] text-muted">weight {s.weight}</span>
                  </div>
                  <p className="text-[11px] text-muted">{s.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-2 rounded border border-edge bg-ink/60 p-2 text-[11px] text-muted">
            {trust.advisory_note}
          </p>
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card">
      <span className="label">{label}</span>
      <p className="mt-1 font-mono text-xl text-slate-100">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-muted">{hint}</p>}
    </div>
  );
}
