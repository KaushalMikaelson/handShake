import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, type SystemStatus } from "./services/api";
import BuyerPage from "./pages/BuyerPage";
import MerchantPage from "./pages/MerchantPage";
import ApprovalsPage from "./pages/ApprovalsPage";
import AuditPage from "./pages/AuditPage";
import { Pill } from "./components/ui";

const TABS = [
  { to: "/buyer", label: "Buyer" },
  { to: "/approvals", label: "Approvals" },
  { to: "/merchant", label: "Merchant" },
  { to: "/audit", label: "Audit Trail" },
];

export default function App() {
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    api.systemStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  return (
    <div className="min-h-screen">
      <header className="border-b border-edge bg-panel/60 backdropblur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-5 py-3">
          <div className="mr-auto">
            <h1 className="text-sm font-semibold text-slate-100">Bounded AI-to-AI Commerce</h1>
            <p className="text-[11px] text-muted">
              Buyer Agent × Merchant Growth Agent, gated by a deterministic policy engine
            </p>
          </div>

          {status && (
            <div className="flex items-center gap-2">
              <Pill tone={status.payments.live ? "pass" : "warn"}>
                payments: {status.payments.mode}
              </Pill>
              <Pill tone={status.llm.live ? "pass" : "warn"}>llm: {status.llm.mode}</Pill>
            </div>
          )}

          <nav className="flex gap-1">
            {TABS.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-xs font-medium transition ${
                    isActive ? "bg-accent text-white" : "text-muted hover:bg-edge/50 hover:text-slate-200"
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-5">
        <Routes>
          <Route path="/" element={<Navigate to="/buyer" replace />} />
          <Route path="/buyer" element={<BuyerPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/merchant" element={<MerchantPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Routes>
      </main>

      {status && (
        <footer className="mx-auto max-w-7xl px-5 pb-8 pt-2">
          <p className="text-[11px] leading-relaxed text-muted">
            <strong className="text-slate-400">Architectural rule:</strong> the LLM has no tool,
            function, or route that reaches the payment gateway. The only interfaces between the AI
            layer and money are the permission check and the policy engine — both plain Python with
            no model in the loop.
          </p>
        </footer>
      )}
    </div>
  );
}
