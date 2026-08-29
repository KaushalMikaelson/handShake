import type { PolicyDecision } from "../services/api";
import { Pill } from "./ui";

/**
 * Per-rule policy report.
 *
 * Shows every rule the engine evaluated, in the order it ran them, and names
 * the one that failed. This is the view that makes "safe by construction"
 * legible instead of a claim in a README.
 */
export function PolicyReport({ policy }: { policy: PolicyDecision }) {
  const blocked = policy.decision === "BLOCKED";

  return (
    <div className="space-y-3">
      <div
        className={`rounded-lg border p-3 ${
          blocked ? "border-danger/40 bg-danger/8" : "border-ok/35 bg-ok/6"
        }`}
      >
        <div className="mb-1.5 flex flex-wrap items-center gap-2">
          <Pill tone={blocked ? "danger" : "ok"}>{policy.decision}</Pill>
          {policy.failed_rule && (
            <code className="font-mono text-2xs text-danger">{policy.failed_rule}</code>
          )}
        </div>
        <p className="text-xs leading-relaxed text-body">{policy.reason}</p>
      </div>

      <ol className="space-y-1">
        {policy.checks.map((c, i) => (
          <li
            key={c.rule}
            className="flex items-start gap-2.5 rounded-lg border border-line bg-raised/40 p-2.5"
          >
            <span className="mt-0.5 font-mono text-2xs text-subtle">{i + 1}</span>
            <span
              className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${
                c.passed ? "bg-ok/15 text-ok" : "bg-danger/15 text-danger"
              }`}
            >
              {c.passed ? "✓" : "✕"}
            </span>
            <div className="min-w-0 flex-1">
              <code className="font-mono text-2xs text-subtle">{c.rule}</code>
              <p className="mt-0.5 text-xs leading-relaxed text-body">{c.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
