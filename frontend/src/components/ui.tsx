import type { ButtonHTMLAttributes, ReactNode } from "react";

/* ------------------------------------------------------------------ card */
export function Card({
  title,
  subtitle,
  right,
  children,
  className = "",
  padded = true,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || right) && (
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-bold tracking-tight text-strong flex items-center gap-2">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-subtle font-normal">{subtitle}</p>}
          </div>
          {right && <div className="shrink-0">{right}</div>}
        </header>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ pill */
const TONES: Record<string, string> = {
  ok: "bg-ok/15 text-ok ring-1 ring-inset ring-ok/30",
  danger: "bg-danger/15 text-danger ring-1 ring-inset ring-danger/30",
  warn: "bg-warn/15 text-warn ring-1 ring-inset ring-warn/30",
  brand: "bg-brand/15 text-brand ring-1 ring-inset ring-brand/30",
  mute: "bg-raised text-subtle ring-1 ring-inset ring-line",
};

export function Pill({ tone = "mute", children }: { tone?: string; children: ReactNode }) {
  return <span className={`pill ${TONES[tone] ?? TONES.mute}`}>{children}</span>;
}

/** Map a backend status string onto a visual tone. */
export function statusTone(status: string): string {
  const s = (status ?? "").toLowerCase();
  if (["completed", "captured", "approved", "auto_approve", "ok", "pass", "granted", "razorpay_test"].some((k) => s.includes(k)))
    return "ok";
  if (["blocked", "denied", "rejected", "failed", "invalid", "locked"].some((k) => s.includes(k)))
    return "danger";
  if (["pending", "awaiting", "requires_approval", "verification", "clarification", "ignored"].some((k) => s.includes(k)))
    return "warn";
  return "brand";
}

/* ---------------------------------------------------------------- button */
export function Button({
  variant = "secondary",
  loading = false,
  size = "md",
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  loading?: boolean;
  size?: "sm" | "md";
}) {
  const base = { primary: "btn-primary", secondary: "btn-secondary", danger: "btn-danger", ghost: "btn-ghost" }[variant];
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      aria-busy={loading || undefined}
      className={`${base} ${size === "sm" ? "btn-sm" : ""} ${className}`}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={`h-4 w-4 animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

/* ----------------------------------------------------------------- meter */
export function Meter({
  used,
  total,
  label,
  caption,
}: {
  used: number;
  total: number;
  label: string;
  caption?: ReactNode;
}) {
  const pct = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;
  const tone = pct >= 90 ? "bg-danger" : pct >= 70 ? "bg-warn" : "bg-ok";
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="label">{label}</span>
        <span className="font-mono text-2xs font-bold text-strong">{pct}%</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-raised border border-line/40 shadow-inner"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div className={`h-full rounded-full transition-all duration-700 ease-out ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      {caption && <p className="text-xs text-subtle">{caption}</p>}
    </div>
  );
}

/* ------------------------------------------------------------ empty/error */
export function Empty({ icon = "◈", title, children }: { icon?: string; title?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <div className="mb-3.5 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/10 text-xl font-bold text-brand shadow-sm">
        {icon}
      </div>
      {title && <p className="text-base font-bold text-strong">{title}</p>}
      {children && <p className="mt-1.5 max-w-md text-xs leading-relaxed text-subtle">{children}</p>}
    </div>
  );
}

export function ErrorBanner({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="flex items-start gap-3 rounded-xl border border-danger/40 bg-danger/10 p-4 shadow-sm" role="alert">
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-danger text-2xs font-bold text-white shadow-xs">
        !
      </span>
      <p className="min-w-0 flex-1 text-xs font-medium leading-relaxed text-danger">{error}</p>
      {onRetry && (
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- skeleton */
export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="card space-y-3 p-5">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={`h-3.5 ${i % 2 ? "w-4/5" : "w-full"}`} />
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------- misc */
export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: string }) {
  return (
    <div className="card p-5">
      <span className="label">{label}</span>
      <p className={`mt-2 font-mono text-2xl font-bold tracking-tight ${tone ? `text-${tone}` : "text-strong"}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-subtle">{hint}</p>}
    </div>
  );
}

export function Row({ k, v, mono = false }: { k: ReactNode; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <dt className="text-xs font-medium text-subtle">{k}</dt>
      <dd className={`text-right text-xs font-semibold text-strong ${mono ? "font-mono" : ""}`}>{v}</dd>
    </div>
  );
}

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-max max-w-xs
                   -translate-x-1/2 rounded-lg border border-line bg-surface px-2.5 py-1.5
                   text-2xs font-medium text-strong opacity-0 shadow-lg transition-opacity
                   group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {label}
      </span>
    </span>
  );
}
