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
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-strong">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-subtle">{subtitle}</p>}
          </div>
          {right && <div className="shrink-0">{right}</div>}
        </header>
      )}
      <div className={padded ? "p-4" : ""}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ pill */
const TONES: Record<string, string> = {
  ok: "bg-ok/12 text-ok ring-1 ring-inset ring-ok/25",
  danger: "bg-danger/12 text-danger ring-1 ring-inset ring-danger/25",
  warn: "bg-warn/12 text-warn ring-1 ring-inset ring-warn/25",
  brand: "bg-brand/12 text-brand ring-1 ring-inset ring-brand/25",
  mute: "bg-raised text-subtle ring-1 ring-inset ring-line",
};

export function Pill({ tone = "mute", children }: { tone?: string; children: ReactNode }) {
  return <span className={`pill ${TONES[tone] ?? TONES.mute}`}>{children}</span>;
}

/** Map a backend status string onto a visual tone. */
export function statusTone(status: string): string {
  const s = (status ?? "").toLowerCase();
  if (["completed", "captured", "approved", "auto_approve", "ok", "pass", "granted"].some((k) => s.includes(k)))
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
    <svg className={`h-3.5 w-3.5 animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
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
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="label">{label}</span>
        <span className="font-mono text-2xs text-subtle">{pct}%</span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-raised"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div className={`h-full rounded-full transition-all duration-700 ease-out ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      {caption && <p className="mt-1.5 text-xs text-subtle">{caption}</p>}
    </div>
  );
}

/* ------------------------------------------------------------ empty/error */
export function Empty({ icon = "◌", title, children }: { icon?: string; title?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-raised text-lg text-subtle">
        {icon}
      </div>
      {title && <p className="text-sm font-medium text-strong">{title}</p>}
      {children && <p className="mt-1 max-w-sm text-xs leading-relaxed text-subtle">{children}</p>}
    </div>
  );
}

export function ErrorBanner({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="flex items-start gap-2.5 rounded-lg border border-danger/40 bg-danger/8 p-3" role="alert">
      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-danger/20 text-2xs font-bold text-danger">
        !
      </span>
      <p className="min-w-0 flex-1 text-xs leading-relaxed text-danger">{error}</p>
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
    <div className="card space-y-3 p-4">
      <Skeleton className="h-3 w-1/3" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={`h-3 ${i % 2 ? "w-4/5" : "w-full"}`} />
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------- misc */
export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: string }) {
  return (
    <div className="card p-4">
      <span className="label">{label}</span>
      <p className={`mt-1.5 font-mono text-xl font-semibold ${tone ? `text-${tone}` : "text-strong"}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-subtle">{hint}</p>}
    </div>
  );
}

export function Row({ k, v, mono = false }: { k: ReactNode; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <dt className="text-xs text-subtle">{k}</dt>
      <dd className={`text-right text-xs text-body ${mono ? "font-mono" : ""}`}>{v}</dd>
    </div>
  );
}

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 w-max max-w-xs
                   -translate-x-1/2 rounded-lg border border-line bg-surface px-2 py-1
                   text-2xs text-body opacity-0 shadow-lift transition-opacity
                   group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {label}
      </span>
    </span>
  );
}
