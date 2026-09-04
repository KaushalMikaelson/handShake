import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";
import { api, type SystemStatus } from "../services/api";
import { Pill, Tooltip } from "./ui";
import { Wordmark } from "../pages/LoginPage";

interface NavItem {
  to: string;
  view: string;
  label: string;
  icon: string;
  hint: string;
}

const NAV: NavItem[] = [
  { to: "/buyer", view: "buyer", label: "Buyer Agent", icon: "◈", hint: "Shop with bounded AI" },
  { to: "/approvals", view: "approvals", label: "Human Approvals", icon: "◑", hint: "Decide pending purchases" },
  { to: "/merchant", view: "merchant", label: "Merchant Growth", icon: "◭", hint: "Upsell & bundle opportunities" },
  { to: "/audit", view: "audit", label: "Audit Trail & Drills", icon: "≡", hint: "Immutable event history" },
];

export function AppShell({
  children,
  pendingApprovals = 0,
}: {
  children: ReactNode;
  pendingApprovals?: number;
}) {
  const { user, can, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const toast = useToast();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.systemStatus().then(setStatus).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const visible = NAV.filter((n) => can(n.view));

  async function handleLogout() {
    await logout();
    toast.info("Signed out", "Your session was revoked on the server.");
  }

  return (
    <div className="flex min-h-screen">
      {/* -------------------------------------------------- sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-surface shadow-xs
                    transition-transform duration-200 lg:translate-x-0
                    ${navOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="border-b border-line px-5 py-5 flex items-center justify-between">
          <Wordmark />
        </div>

        <nav className="flex-1 space-y-1 p-3.5" aria-label="Main Navigation">
          {visible.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setNavOpen(false)}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all ${
                  isActive
                    ? "bg-brand/12 text-brand ring-1 ring-brand/30 shadow-sm"
                    : "text-body hover:bg-raised hover:text-strong"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`w-5 text-center text-base ${isActive ? "text-brand" : "text-subtle"}`}>
                    {item.icon}
                  </span>
                  <span className="flex-1">{item.label}</span>
                  {item.view === "approvals" && pendingApprovals > 0 && (
                    <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-warn px-1.5 text-2xs font-extrabold text-white shadow-xs">
                      {pendingApprovals}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* integration mode badges */}
        {status && (
          <div className="space-y-2 border-t border-line p-4 bg-raised/40">
            <span className="label text-2xs block">System Status</span>
            <div className="flex items-center justify-between gap-2">
              <span className="text-2xs font-semibold text-subtle">Razorpay</span>
              <Tooltip label={status.payments.note}>
                <Pill tone={status.payments.live ? "ok" : "warn"}>
                  <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse mr-1 inline-block" />
                  {status.payments.mode}
                </Pill>
              </Tooltip>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-2xs font-semibold text-subtle">LLM Engine</span>
              <Tooltip label={status.llm.note}>
                <Pill tone={status.llm.live ? "ok" : "warn"}>
                  <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse mr-1 inline-block" />
                  {status.llm.mode}
                </Pill>
              </Tooltip>
            </div>
          </div>
        )}

        {/* -------------------------------------------- user menu */}
        <div ref={menuRef} className="relative border-t border-line p-3.5">
          <button
            onClick={() => setMenuOpen((o) => !o)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="flex w-full items-center gap-3 rounded-xl p-2 text-left transition hover:bg-raised"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand/15 text-xs font-bold text-brand shadow-sm">
              {user?.name?.slice(0, 2).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-bold text-strong">{user?.name}</span>
              <span className="block truncate text-2xs capitalize font-medium text-subtle">{user?.role} Role</span>
            </span>
            <span className="text-2xs text-subtle">{menuOpen ? "▾" : "▴"}</span>
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute bottom-full left-3 right-3 mb-2 animate-fade-up overflow-hidden rounded-xl border border-line bg-surface shadow-lg"
            >
              <p className="truncate border-b border-line px-3.5 py-2.5 font-mono text-2xs text-subtle">
                {user?.email}
              </p>
              <button
                role="menuitem"
                onClick={() => {
                  toggle();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-xs font-medium text-body transition hover:bg-raised"
              >
                <span className="w-4 text-center">{theme === "dark" ? "☀" : "☾"}</span>
                {theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
              </button>
              <button
                role="menuitem"
                onClick={handleLogout}
                className="flex w-full items-center gap-2.5 border-t border-line px-3.5 py-2.5 text-left text-xs font-semibold text-danger transition hover:bg-danger/10"
              >
                <span className="w-4 text-center">⏻</span>
                Sign Out
              </button>
            </div>
          )}
        </div>
      </aside>

      {navOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-xs lg:hidden"
          onClick={() => setNavOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* -------------------------------------------------- content */}
      <div className="flex min-w-0 flex-1 flex-col lg:ml-64">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-canvas/90 px-5 py-3.5 backdrop-blur-md lg:hidden">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setNavOpen(true)}
              className="btn-ghost btn-sm"
              aria-label="Open navigation"
            >
              ☰
            </button>
            <Wordmark />
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 p-5 sm:p-7">{children}</main>

        <footer className="mx-auto w-full max-w-7xl px-5 pb-7 sm:px-7">
          <p className="text-2xs leading-relaxed text-subtle border-t border-line pt-4 font-medium">
            <strong className="text-strong font-bold">Architectural Guarantee:</strong> The LLM has zero direct route to payment execution APIs. Every transaction is bounded, policy-checked, and deterministically verified in pure Python before invoking Razorpay.
          </p>
        </footer>
      </div>
    </div>
  );
}
