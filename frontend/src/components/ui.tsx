import type { ReactNode } from "react";

export function Card({
  title,
  subtitle,
  right,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || right) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-sm font-semibold text-slate-100">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

const TONES: Record<string, string> = {
  pass: "bg-pass/15 text-pass",
  fail: "bg-fail/15 text-fail",
  warn: "bg-warn/15 text-warn",
  info: "bg-accent/15 text-accent",
  mute: "bg-edge text-muted",
};

export function Pill({ tone = "mute", children }: { tone?: keyof typeof TONES | string; children: ReactNode }) {
  return <span className={`pill ${TONES[tone] ?? TONES.mute}`}>{children}</span>;
}

/** Maps a backend status string onto a visual tone. */
export function statusTone(status: string): string {
  const s = status.toLowerCase();
  if (["completed", "captured", "approved", "auto_approve", "ok", "pass"].some((k) => s.includes(k)))
    return "pass";
  if (["blocked", "denied", "rejected", "failed", "invalid"].some((k) => s.includes(k))) return "fail";
  if (["pending", "awaiting", "requires_approval", "verification"].some((k) => s.includes(k)))
    return "warn";
  return "info";
}

export function Meter({ used, total, label }: { used: number; total: number; label: string }) {
  const pct = total ? Math.min(100, Math.round((used / total) * 100)) : 0;
  const tone = pct >= 90 ? "bg-fail" : pct >= 70 ? "bg-warn" : "bg-pass";
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="label">{label}</span>
        <span className="text-xs text-muted">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-edge">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-xs text-muted">{children}</p>;
}

export function ErrorBanner({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <div className="rounded-md border border-fail/40 bg-fail/10 p-3 text-xs text-fail">{error}</div>
  );
}
