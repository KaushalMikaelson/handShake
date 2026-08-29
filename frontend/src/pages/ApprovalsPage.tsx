import { useEffect, useState } from "react";
import { api, type Approval } from "../services/api";
import { formatINR, formatTime } from "../services/format";
import { Card, Empty, ErrorBanner, Pill, statusTone } from "../components/ui";
import { PolicyReport } from "../components/PolicyReport";

/**
 * The human approval gate (US-7).
 *
 * Approve and Reject are the only two actions. There is deliberately no
 * "approve after timeout" affordance: an untouched request stays pending.
 */
export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.approvals().then(setApprovals).catch((e) => setError(String(e)));
  useEffect(() => { load(); }, []);

  async function decide(id: string, decision: "approve" | "reject") {
    setBusy(id);
    setError(null);
    try {
      await api.decide(id, decision);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  const pending = approvals.filter((a) => a.status === "PENDING");
  const settled = approvals.filter((a) => a.status !== "PENDING");

  return (
    <div className="space-y-4">
      <ErrorBanner error={error} />

      <Card
        title="Pending approvals"
        subtitle="Purchases the agent prepared but may not execute on its own"
        right={<Pill tone={pending.length ? "warn" : "mute"}>{pending.length} waiting</Pill>}
      >
        {pending.length === 0 ? (
          <Empty>Nothing waiting. Run a purchase above your approval threshold to create one.</Empty>
        ) : (
          <div className="space-y-3">
            {pending.map((a) => (
              <ApprovalCard key={a.approval_id} approval={a} busy={busy === a.approval_id} onDecide={decide} />
            ))}
          </div>
        )}
      </Card>

      <Card title="Decision history">
        {settled.length === 0 ? (
          <Empty>No decisions yet.</Empty>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-edge text-left text-muted">
                <th className="py-1.5 font-medium">Amount</th>
                <th className="font-medium">Product</th>
                <th className="font-medium">Decision</th>
                <th className="font-medium">By</th>
                <th className="font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {settled.map((a) => (
                <tr key={a.approval_id} className="border-b border-edge/40">
                  <td className="py-1.5 font-mono">{formatINR(a.amount)}</td>
                  <td className="text-slate-300">{a.context?.product?.name ?? "—"}</td>
                  <td><Pill tone={statusTone(a.status)}>{a.status}</Pill></td>
                  <td className="text-muted">{a.decided_by ?? "—"}</td>
                  <td className="text-muted">{a.decided_at ? formatTime(a.decided_at) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function ApprovalCard({
  approval,
  busy,
  onDecide,
}: {
  approval: Approval;
  busy: boolean;
  onDecide: (id: string, d: "approve" | "reject") => void;
}) {
  const ctx = approval.context ?? {};
  return (
    <div className="rounded-lg border border-warn/30 bg-warn/5 p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">{ctx.product?.name ?? "Purchase"}</h3>
          <p className="text-[11px] text-muted">
            {ctx.merchant?.name} · requested {formatTime(approval.created_at)}
          </p>
        </div>
        <span className="font-mono text-lg text-slate-100">{formatINR(approval.amount)}</span>
      </div>

      <div className="mb-3 grid gap-2 text-xs sm:grid-cols-3">
        <Fact label="Spent today" value={formatINR(ctx.spent_today ?? 0)} />
        <Fact label="Remaining after" value={formatINR(ctx.remaining_after_purchase ?? 0)} />
        <Fact label="Merchant trust" value={ctx.trust ? `${ctx.trust.score}/100` : "—"} />
      </div>

      {ctx.agent_reasoning && (
        <div className="mb-3">
          <span className="label">Agent reasoning</span>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-300">{ctx.agent_reasoning}</p>
        </div>
      )}

      {ctx.policy && (
        <details className="mb-3">
          <summary className="cursor-pointer text-xs text-accent">Policy check detail</summary>
          <div className="mt-2"><PolicyReport policy={ctx.policy} /></div>
        </details>
      )}

      <div className="flex gap-2">
        <button className="btn-primary" disabled={busy} onClick={() => onDecide(approval.approval_id, "approve")}>
          {busy ? "Working…" : "Approve"}
        </button>
        <button className="btn-danger" disabled={busy} onClick={() => onDecide(approval.approval_id, "reject")}>
          Reject
        </button>
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-edge bg-ink/50 p-2">
      <span className="label">{label}</span>
      <p className="mt-0.5 font-mono text-slate-200">{value}</p>
    </div>
  );
}
