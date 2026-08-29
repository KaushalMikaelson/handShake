import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { AppShell } from "./components/AppShell";
import { Spinner } from "./components/ui";
import { api } from "./services/api";
import LoginPage from "./pages/LoginPage";
import BuyerPage from "./pages/BuyerPage";
import MerchantPage from "./pages/MerchantPage";
import ApprovalsPage from "./pages/ApprovalsPage";
import AuditPage from "./pages/AuditPage";

export default function App() {
  const { user, loading, can } = useAuth();
  const [pending, setPending] = useState(0);
  const location = useLocation();

  // Keep the sidebar badge honest: refresh the pending count on navigation and
  // whenever a screen reports that it changed something.
  const refreshPending = useCallback(() => {
    if (!user || !can("approvals")) return;
    api
      .approvals()
      .then((list) => setPending(list.filter((a) => a.status === "PENDING").length))
      .catch(() => undefined);
  }, [user, can]);

  useEffect(refreshPending, [refreshPending, location.pathname]);

  // Boot: don't flash the login page while the session check is in flight.
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-subtle">
          <Spinner />
          Restoring session…
        </div>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  // Land each role somewhere it is actually allowed to be.
  const home = can("buyer") ? "/buyer" : can("merchant") ? "/merchant" : "/audit";

  return (
    <AppShell pendingApprovals={pending}>
      <Routes>
        <Route path="/" element={<Navigate to={home} replace />} />
        <Route path="/login" element={<Navigate to={home} replace />} />
        <Route
          path="/buyer"
          element={can("buyer") ? <BuyerPage onChanged={refreshPending} /> : <Navigate to={home} replace />}
        />
        <Route
          path="/approvals"
          element={can("approvals") ? <ApprovalsPage onChanged={refreshPending} /> : <Navigate to={home} replace />}
        />
        <Route
          path="/merchant"
          element={can("merchant") ? <MerchantPage /> : <Navigate to={home} replace />}
        />
        <Route path="/audit" element={can("audit") ? <AuditPage /> : <Navigate to={home} replace />} />
        <Route path="*" element={<Navigate to={home} replace />} />
      </Routes>
    </AppShell>
  );
}
