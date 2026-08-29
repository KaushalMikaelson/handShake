import { useState, type FormEvent } from "react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Button, ErrorBanner } from "../components/ui";
import { ApiError } from "../services/api";

/** Demo logins, surfaced so a reviewer can be inside the app in one click. */
const DEMO_ACCOUNTS = [
  {
    email: "aditi@handshake.demo",
    role: "Buyer",
    blurb: "Shop with the agent, set policy, approve purchases",
  },
  {
    email: "merchant@audiohub.demo",
    role: "Merchant",
    blurb: "Growth opportunities, revenue, trust profile",
  },
  {
    email: "admin@handshake.demo",
    role: "Admin",
    blurb: "Read-only view of both sides — no financial authority",
  },
];
const DEMO_PASSWORD = "Demo@1234";

export default function LoginPage() {
  const { login, register } = useAuth();
  const toast = useToast();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(email, password);
        toast.success("Signed in");
      } else {
        await register(email, name, password);
        toast.success("Account created", "Your agent starts in ask-me-first mode.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function useDemo(demoEmail: string) {
    setMode("login");
    setEmail(demoEmail);
    setPassword(DEMO_PASSWORD);
    setError(null);
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* ---------------- narrative panel ---------------- */}
      <div className="relative hidden overflow-hidden border-r border-line bg-surface lg:flex lg:flex-col lg:justify-between lg:p-10">
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full opacity-20 blur-3xl"
          style={{ background: "radial-gradient(circle, rgb(var(--brand)), transparent 70%)" }}
        />
        <div className="relative">
          <Wordmark />
          <h1 className="mt-10 max-w-lg text-3xl font-semibold leading-tight tracking-tight text-strong">
            An AI that can spend money only within rules its owner controls.
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-subtle">
            An autonomous Buyer Agent discovers, evaluates and purchases from an AI-powered
            Merchant Growth Agent over Razorpay — with every financial action gated by a
            deterministic policy engine.
          </p>

          <ul className="mt-8 space-y-3">
            {[
              ["Bounded autonomy", "Auto-buy small, ask above a threshold, block over the limit"],
              ["Human in the loop", "Approve or reject, with the full reasoning in front of you"],
              ["Complete audit trail", "Every agent decision, timestamped and explained"],
              ["Fails safely", "Timeouts verify instead of retrying; replays are ignored"],
            ].map(([title, detail]) => (
              <li key={title} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-ok/15 text-[9px] font-bold text-ok">
                  ✓
                </span>
                <span className="text-sm text-body">
                  <strong className="font-medium text-strong">{title}</strong>
                  <span className="text-subtle"> — {detail}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-2xs leading-relaxed text-subtle">
          The LLM has no tool, function, or route that reaches the payment gateway. The only
          interfaces between the AI layer and money are the permission check and the policy
          engine — both plain Python, with no model in the loop.
        </p>
      </div>

      {/* ---------------- form panel ---------------- */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm animate-fade-up">
          <div className="lg:hidden">
            <Wordmark />
          </div>

          <h2 className="mt-8 text-xl font-semibold tracking-tight text-strong lg:mt-0">
            {mode === "login" ? "Sign in" : "Create an account"}
          </h2>
          <p className="mt-1 text-sm text-subtle">
            {mode === "login"
              ? "Use a demo account below, or your own credentials."
              : "New agents start in ask-me-first mode with a small budget."}
          </p>

          <form onSubmit={submit} className="mt-6 space-y-3">
            {mode === "register" && (
              <Field label="Name" htmlFor="name">
                <input
                  id="name"
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  required
                  autoComplete="name"
                />
              </Field>
            )}

            <Field label="Email" htmlFor="email">
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
              />
            </Field>

            <Field
              label="Password"
              htmlFor="password"
              hint={mode === "register" ? "8+ chars, mixed case, one digit" : undefined}
            >
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            </Field>

            <ErrorBanner error={error} />

            <Button type="submit" variant="primary" loading={busy} className="w-full">
              {mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <p className="mt-4 text-center text-xs text-subtle">
            {mode === "login" ? "No account? " : "Already have one? "}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="font-medium text-brand hover:underline"
            >
              {mode === "login" ? "Create one" : "Sign in"}
            </button>
          </p>

          <div className="mt-8">
            <div className="mb-2.5 flex items-center gap-2">
              <span className="h-px flex-1 bg-line" />
              <span className="label">Demo accounts</span>
              <span className="h-px flex-1 bg-line" />
            </div>
            <div className="space-y-1.5">
              {DEMO_ACCOUNTS.map((a) => (
                <button
                  key={a.email}
                  type="button"
                  onClick={() => useDemo(a.email)}
                  className="group w-full rounded-lg border border-line bg-surface p-2.5 text-left
                             transition-all hover:border-brand/50 hover:bg-brand/5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-strong">{a.role}</span>
                    <span className="font-mono text-2xs text-subtle group-hover:text-brand">
                      {a.email}
                    </span>
                  </div>
                  <p className="mt-0.5 text-2xs text-subtle">{a.blurb}</p>
                </button>
              ))}
            </div>
            <p className="mt-2 text-center font-mono text-2xs text-subtle">
              password: {DEMO_PASSWORD}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <label htmlFor={htmlFor} className="label">
          {label}
        </label>
        {hint && <span className="text-2xs text-subtle">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-sm font-bold text-white shadow-sm">
        ⇄
      </div>
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight text-strong">handShake</p>
        <p className="text-2xs text-subtle">Bounded AI-to-AI Commerce</p>
      </div>
    </div>
  );
}
