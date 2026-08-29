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
  { to: "/buyer", view: "buyer", label: "Buyer", icon: "◈", hint: "Shop with your agent" },
  { to: "/approvals", view: "approvals", label: "Approvals", icon: "◑", hint: "Decide pending purchases" },
  { to: "/merchant", view: "merchant", label: "Merchant", icon: "◭", hint: "Growth opportunities" },
  { to: "/audit", view: "audit", label: "Audit Trail", icon: "≡", hint: "Every decision, explained" },
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

  // Close the user menu on an outside click or Escape - basic menu hygiene
  // that is conspicuous by its absence when missing.
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
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-surface
                    transition-transform duration-200 lg:translate-x-0
                    ${navOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="border-b border-line px-4 py-4">
          <Wordmark />
        </div>

        <nav className="flex-1 space-y-0.5 p-3" aria-label="Main">
          {visible.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setNavOpen(false)}
              className={({ isActive }) =>
                `group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-all ${
                  isActive
                    ? "bg-brand/10 font-medium text-brand ring-1 ring-inset ring-brand/20"
                    : "text-body hover:bg-raised hover:text-strong"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`w-4 text-center text-sm ${isActive ? "text-brand" : "text-subtle"}`}>
                    {item.icon}
                  </span>
                  <span className="flex-1">{item.label}</span>
                  {item.view === "approvals" && pendingApprovals > 0 && (
                    <span className="animate-pulse-ring flex h-4 min-w-4 items-center justify-center rounded-full bg-warn px-1 text-[10px] font-bold text-white">
                      {pendingApprovals}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* integration mode - so a demo can never quietly overclaim */}
        {status && (
          <div className="space-y-1.5 border-t border-line p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-2xs text-subtle">Payments</span>
              <Tooltip label={status.payments.note}>
                <Pill tone={status.payments.live ? "ok" : "warn"}>{status.payments.mode}</Pill>
              </Tooltip>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-2xs text-subtle">Agents</span>
              <Tooltip label={status.llm.note}>
                <Pill tone={status.llm.live ? "ok" : "warn"}>{status.llm.mode}</Pill>
              </Tooltip>
            </div>
          </div>
        )}

        {/* -------------------------------------------- user menu */}
        <div ref={menuRef} className="relative border-t border-line p-3">
          <button
            onClick={() => setMenuOpen((o) => !o)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left transition hover:bg-raised"
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand/15 text-2xs font-bold text-brand">
              {user?.name?.slice(0, 2).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-medium text-strong">{user?.name}</span>
              <span className="block truncate text-2xs capitalize text-subtle">{user?.role}</span>
            </span>
            <span className="text-2xs text-subtle">{menuOpen ? "▾" : "▴"}</span>
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute bottom-full left-3 right-3 mb-1 animate-fade-up overflow-hidden rounded-lg border border-line bg-surface shadow-lift"
            >
              <p className="truncate border-b border-line px-3 py-2 font-mono text-2xs text-subtle">
                {user?.email}
              </p>
              <button
                role="menuitem"
                onClick={() => {
                  toggle();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-body transition hover:bg-raised"
              >
                <span className="w-4 text-center">{theme === "dark" ? "☀" : "☾"}</span>
                {theme === "dark" ? "Light mode" : "Dark mode"}
              </button>
              <button
                role="menuitem"
                onClick={handleLogout}
                className="flex w-full items-center gap-2 border-t border-line px-3 py-2 text-left text-xs text-danger transition hover:bg-danger/8"
              >
                <span className="w-4 text-center">⏻</span>
                Sign out
              </button>
            </div>
          )}
        </div>
      </aside>

      {navOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setNavOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* -------------------------------------------------- content */}
      <div className="flex min-w-0 flex-1 flex-col lg:ml-60">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-canvas/85 px-4 py-2.5 backdrop-blur lg:hidden">
          <button
            onClick={() => setNavOpen(true)}
            className="btn-ghost btn-sm"
            aria-label="Open navigation"
          >
            ☰
          </button>
          <Wordmark />
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">{children}</main>

        <footer className="mx-auto w-full max-w-7xl px-4 pb-6 sm:px-6">
          <p className="text-2xs leading-relaxed text-subtle">
            <strong className="text-body">Architectural rule:</strong> the LLM has no tool,
            function, or route that reaches the payment gateway. The only interfaces between the
            AI layer and money are the permission check and the policy engine — both plain
            Python, with no model in the loop.
          </p>
        </footer>
      </div>
    </div>
  );
}
