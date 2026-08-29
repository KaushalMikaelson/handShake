import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Approval } from "../services/api";
import { formatINR, formatTime } from "../services/format";
import { useToast } from "../context/ToastContext";
import {
  Button,
  Card,
  Empty,
  ErrorBanner,
  Pill,
  SkeletonCard,
  statusTone,
} from "../components/ui";
import { PolicyReport } from "../components/PolicyReport";

/**
 * The human approval gate (US-7).
 *
 * Approve and Reject are the only two actions, and rejection asks for
 * confirmation because it ends the flow irreversibly. There is deliberately no
 * "approve after timeout" affordance: an untouched request stays pending.
 */
export default function ApprovalsPage({ onChanged }: { onChanged?: () => void }) {
  const toast = useToast();
  const [approvals, setApprovals] = useState<Approval[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      api
        .approvals()
        .then((a) => {
          setApprovals(a);
          setError(null);
        })
        .catch((e) => setError(e instanceof ApiError ? e.message : String(e))),
    [],
  );

  useEffect(() => {
    load();
  }, [load]);

  async function decide(id: string, decision: "approve" | "reject") {
    setBusy(id);
    try {
      const r = await api.decide(id, decision);
      await load();
      onChanged?.();
      if (decision === "approve") toast.success("Approved", r.message);
      else toast.info("Rejected", "No payment was attempted.");
    } catch (e) {
      toast.error("Could not record decision", e instanceof ApiError ? e.message : undefined);
    } finally {
      setBusy(null);
    }
  }

  const pending = (approvals ?? []).filter((a) => a.status === "PENDING");
  const settled = (approvals ?? []).filter((a) => a.status !== "PENDING");

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <ErrorBanner error={error} onRetry={load} />

      <Card
        title="Pending approvals"
        subtitle="Purchases your agent prepared but may not execute alone"
        right={<Pill tone={pending.length ? "warn" : "mute"}>{pending.length} waiting</Pill>}
      >
        {approvals === null ? (
          <SkeletonCard rows={4} />
        ) : pending.length === 0 ? (
          <Empty icon="✓" title="Nothing waiting">
            Run a purchase above your approval threshold on the Buyer screen to create one.
          </Empty>
        ) : (
          <div className="space-y-3">
            {pending.map((a) => (
              <ApprovalCard
                key={a.approval_id}
                approval={a}
                busy={busy === a.approval_id}
                onDecide={decide}
              />
            ))}
          </div>
        )}
      </Card>

      <Card title="Decision history" subtitle="Every verdict, attributed to who made it">
        {settled.length === 0 ? (
          <Empty icon="≡">No decisions recorded yet.</Empty>
        ) : (
          <div className="-m-4 overflow-x-auto">
            <table className="w-full min-w-[36rem] text-xs">
              <thead>
                <tr className="border-b border-line text-left">
                  <th className="px-4 py-2 font-medium text-subtle">Amount</th>
                  <th className="py-2 font-medium text-subtle">Product</th>
                  <th className="py-2 font-medium text-subtle">Decision</th>
                  <th className="py-2 font-medium text-subtle">By</th>
                  <th className="px-4 py-2 font-medium text-subtle">When</th>
                </tr>
              </thead>
              <tbody>
                {settled.map((a) => (
                  <tr key={a.approval_id} className="border-b border-line/60 last:border-0">
                    <td className="px-4 py-2 font-mono text-body">{formatINR(a.amount)}</td>
                    <td className="py-2 text-body">{a.context?.product?.name ?? "—"}</td>
                    <td className="py-2">
                      <Pill tone={statusTone(a.status)}>{a.status}</Pill>
                    </td>
                    <td className="py-2 text-subtle">{a.decided_by ?? "—"}</td>
                    <td className="px-4 py-2 text-subtle">
                      {a.decided_at ? formatTime(a.decided_at) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
  const [confirmReject, setConfirmReject] = useState(false);
  const ctx = approval.context ?? {};

  return (
    <div className="animate-fade-up rounded-xl border border-warn/35 bg-warn/5 p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-strong">{ctx.product?.name ?? "Purchase"}</h3>
          <p className="mt-0.5 text-2xs text-subtle">
            {ctx.merchant?.name} · requested {formatTime(approval.created_at)}
          </p>
        </div>
        <span className="font-mono text-lg font-semibold text-strong">
          {formatINR(approval.amount)}
        </span>
      </div>

      <div className="mb-3 grid gap-2 sm:grid-cols-3">
        <Fact label="Spent today" value={formatINR(ctx.spent_today ?? 0)} />
        <Fact label="Remaining after" value={formatINR(ctx.remaining_after_purchase ?? 0)} />
        <Fact label="Merchant trust" value={ctx.trust ? `${ctx.trust.score}/100` : "—"} />
      </div>

      {ctx.agent_reasoning && (
        <div className="mb-3">
          <span className="label">Agent reasoning</span>
          <p className="mt-1 text-xs leading-relaxed text-body">{ctx.agent_reasoning}</p>
        </div>
      )}

      {ctx.bundle?.offered && (
        <div className="mb-3">
          <span className="label">Bundle offered</span>
          <p className="mt-1 text-xs text-body">
            {ctx.bundle.reasoning}{" "}
            <span className="font-mono text-ok">
              {formatINR(ctx.bundle.bundle_price)} ({ctx.bundle.discount_pct}% off)
            </span>
          </p>
        </div>
      )}

      {ctx.policy && (
        <details className="mb-3 group">
          <summary className="cursor-pointer list-none text-xs font-medium text-brand hover:underline">
            <span className="inline-block transition-transform group-open:rotate-90">▸</span> Policy
            check detail ({ctx.policy.checks?.length ?? 0} rules)
          </summary>
          <div className="mt-2.5">
            <PolicyReport policy={ctx.policy} />
          </div>
        </details>
      )}

      {confirmReject ? (
        <div className="rounded-lg border border-danger/40 bg-danger/8 p-3">
          <p className="mb-2.5 text-xs text-body">
            Reject this purchase? The flow ends here, it is logged, and nothing is charged.
          </p>
          <div className="flex gap-2">
            <Button
              variant="danger"
              size="sm"
              loading={busy}
              onClick={() => onDecide(approval.approval_id, "reject")}
            >
              Yes, reject
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmReject(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <Button
            variant="primary"
            loading={busy}
            onClick={() => onDecide(approval.approval_id, "approve")}
          >
            Approve
          </Button>
          <Button variant="danger" disabled={busy} onClick={() => setConfirmReject(true)}>
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-2.5">
      <span className="label">{label}</span>
      <p className="mt-0.5 font-mono text-sm text-strong">{value}</p>
    </div>
  );
}
