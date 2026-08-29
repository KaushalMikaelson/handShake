import type { PolicyDecision } from "../services/api";
import { Pill } from "./ui";

/**
 * Per-rule policy report.
 *
 * Shows every rule the engine evaluated, in the order it ran them, and names
 * the one that failed. This is the screen that makes "safe by construction"
 * legible rather than a claim in a README.
 */
export function PolicyReport({ policy }: { policy: PolicyDecision }) {
  const blocked = policy.decision === "BLOCKED";
  return (
    <div className="space-y-3">
      <div
        className={`rounded-md border p-3 ${
          blocked ? "border-fail/40 bg-fail/10" : "border-pass/30 bg-pass/5"
        }`}
      >
        <div className="mb-1 flex items-center gap-2">
          <Pill tone={blocked ? "fail" : "pass"}>{policy.decision}</Pill>
          {policy.failed_rule && (
            <code className="font-mono text-[11px] text-fail">{policy.failed_rule}</code>
          )}
        </div>
        <p className="text-xs leading-relaxed text-slate-300">{policy.reason}</p>
      </div>

      <ul className="space-y-1">
        {policy.checks.map((c) => (
          <li key={c.rule} className="flex items-start gap-2 rounded border border-edge/60 p-2">
            <span className={`mt-0.5 text-xs ${c.passed ? "text-pass" : "text-fail"}`}>
              {c.passed ? "✓" : "✕"}
            </span>
            <div className="min-w-0 flex-1">
              <code className="font-mono text-[11px] text-slate-400">{c.rule}</code>
              <p className="text-xs text-slate-300">{c.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
