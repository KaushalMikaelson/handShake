import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setUnauthorizedHandler, type AuthState, type AuthUser } from "../services/api";

interface AuthContextValue {
  user: AuthUser | null;
  permittedViews: string[];
  /** True until the initial session check finishes, so we never flash the login page. */
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  logoutEverywhere: () => Promise<void>;
  can: (view: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState | null>(null);
  const [loading, setLoading] = useState(true);

  const apply = useCallback((next: AuthState) => setState(next), []);

  // Restore the session on boot. The cookie is httpOnly, so the only way to
  // know whether we are signed in is to ask the server.
  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((s) => !cancelled && apply(s))
      .catch(() => !cancelled && apply({ authenticated: false, user: null, session_expires_at: null, permitted_views: [] }))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [apply]);

  // A session revoked elsewhere, or expired, drops us back to the login screen
  // rather than leaving the UI showing data it can no longer refresh.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setState({ authenticated: false, user: null, session_expires_at: null, permitted_views: [] });
    });
  }, []);

  const login = useCallback(
    async (email: string, password: string) => apply(await api.login(email, password)),
    [apply],
  );

  const register = useCallback(
    async (email: string, name: string, password: string) =>
      apply(await api.register(email, name, password)),
    [apply],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      // Clear locally even if the request failed - the user asked to leave.
      apply({ authenticated: false, user: null, session_expires_at: null, permitted_views: [] });
    }
  }, [apply]);

  const logoutEverywhere = useCallback(async () => {
    try {
      await api.logoutAll();
    } finally {
      apply({ authenticated: false, user: null, session_expires_at: null, permitted_views: [] });
    }
  }, [apply]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: state?.authenticated ? state.user : null,
      permittedViews: state?.permitted_views ?? [],
      loading,
      login,
      register,
      logout,
      logoutEverywhere,
      // The server decides what a role may reach; this only mirrors it so the
      // nav does not offer doors that would 403.
      can: (view: string) => (state?.permitted_views ?? []).includes(view),
    }),
    [state, loading, login, register, logout, logoutEverywhere],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
