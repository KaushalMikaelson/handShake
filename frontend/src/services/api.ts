/** Typed client for the backend. Mirrors the FastAPI OpenAPI contract. */

const API_BASE = import.meta.env.VITE_API_URL ? String(import.meta.env.VITE_API_URL).replace(/\/+$/, "") : "";
const BASE = API_BASE ? `${API_BASE}/api` : "/api";

/** Thrown for any non-2xx response, carrying the status so callers can branch. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

/**
 * Register a global 401 handler.
 *
 * A session can expire or be revoked from another device at any moment. Rather
 * than every screen handling that, one handler bounces the user to the login
 * page, so an expired session can never leave the UI showing stale data it is
 * no longer entitled to.
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler) {
  onUnauthorized = handler;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    // send the httpOnly session cookie (include allows cross-origin when hosted separately)
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (res.status === 401 && !path.startsWith("/auth/")) {
    onUnauthorized?.();
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      // FastAPI puts the human-readable reason in `detail`
      if (typeof body?.detail === "string") message = body.detail;
      else if (Array.isArray(body?.detail)) {
        message = body.detail.map((d: any) => d.msg ?? String(d)).join("; ");
      }
    } catch {
      /* non-JSON error body - keep the status line */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

// ---------- types ----------
export interface Product {
  product_id: string;
  name: string;
  brand: string;
  price: number;
  currency: string;
  category: string;
  stock_available: boolean;
  attributes: string[];
  bundle_eligible: boolean;
  max_discount_pct: number;
  companion_product_ids?: string[];
}

export interface Candidate {
  product_id: string;
  name: string;
  price: number;
  eligible: boolean;
  reasons: string[];
  rejection_reason: string | null;
  justification: string;
  score: number;
}

export interface Recommendation {
  selected_product_id: string | null;
  selected_name: string | null;
  amount: number | null;
  remaining_budget: number | null;
  justification: string;
  candidates: Candidate[];
  decision_factors: string[];
  llm_mode: string;
}

export interface BundleOffer {
  offered: boolean;
  items: { product_id: string; name: string; price: number }[];
  bundle_price: number | null;
  list_price: number | null;
  discount_pct: number;
  reasoning: string;
  llm_mode: string;
}

export interface PolicyCheck {
  rule: string;
  passed: boolean;
  detail: string;
  limit: number | null;
  observed: number | null;
}

export interface PolicyDecision {
  allowed: boolean;
  decision: string;
  failed_rule: string | null;
  reason: string;
  checks: PolicyCheck[];
  evaluated_amount: number;
}

export interface TrustReport {
  merchant_id: string;
  score: number;
  band: string;
  signals: { name: string; passed: boolean; weight: number; detail: string }[];
  advisory_note: string;
}

export interface Transaction {
  id: string;
  purchase_intent_id: string;
  amount: number;
  currency: string;
  status: string;
  razorpay_order_id: string | null;
  razorpay_payment_id: string | null;
  idempotency_key: string;
  failure_reason: string | null;
}

export interface PurchaseIntent {
  intent_id: string;
  buyer_id: string;
  merchant_id: string;
  product_id: string;
  amount: number;
  currency: string;
  reasoning: string;
  status: string;
  created_at: string;
}

export interface Approval {
  approval_id: string;
  purchase_intent_id: string;
  buyer_id: string;
  amount: number;
  status: string;
  context: Record<string, any>;
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
}

export interface ShopResponse {
  status: string;
  stage: string;
  message: string;
  needs_clarification: boolean;
  clarification_question: string | null;
  parsed_intent: Record<string, any> | null;
  recommendation: Recommendation | null;
  bundle: BundleOffer | null;
  trust: TrustReport | null;
  policy: PolicyDecision | null;
  intent: PurchaseIntent | null;
  approval: Approval | null;
  transaction: Transaction | null;
  razorpay_called: boolean;
}

export interface BuyerState {
  buyer_id: string;
  name: string;
  policy: {
    daily_budget: number;
    monthly_budget: number;
    max_transaction: number;
    allowed_categories: string[];
    blocked_categories: string[];
    require_approval_above: number;
    allow_automatic_purchase_below: number;
    autonomy_level: string;
  };
  spent_today: number;
  spent_this_month: number;
  remaining_today: number;
  remaining_this_month: number;
  permissions_allowed: string[];
  permissions_denied: string[];
}

export interface AuditEvent {
  event_id: string;
  sequence: number;
  timestamp: string;
  agent_id: string;
  action: string;
  purchase_intent_id: string | null;
  input_reference: Record<string, any> | null;
  output_reference: Record<string, any> | null;
  reason: string;
  policy_result: Record<string, any> | null;
  status: string;
}

export interface TransactionSummary {
  purchase_intent_id: string;
  status: string;
  amount: number;
  product_id: string;
  created_at: string;
  event_count: number;
  reasoning: string;
  policy_result: PolicyDecision | null;
  final_action: string | null;
}

export interface Opportunity {
  id: string;
  merchant_id: string;
  anchor_product_id: string;
  companion_product_id: string;
  anchor_name: string;
  companion_name: string;
  potential_aov_uplift: number;
  rationale: string;
  status: string;
}

export type UserRole = "buyer" | "merchant" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  buyer_id: string | null;
  merchant_id: string | null;
  last_login_at: string | null;
}

export interface AuthState {
  authenticated: boolean;
  user: AuthUser | null;
  session_expires_at: string | null;
  permitted_views: string[];
}

export interface ActiveSession {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  user_agent: string;
  ip_address: string;
  current: boolean;
}

export interface SystemStatus {
  environment: string;
  payments: { mode: string; live: boolean; note: string; calls_made: number };
  llm: { mode: string; live: boolean; model: string | null; note: string };
  permissions: Record<string, { allowed: string[]; denied: string[] }>;
  security_principles: string[];
}

// ---------- endpoints ----------
export const api = {
  // ---------- auth ----------
  login: (email: string, password: string) =>
    request<AuthState>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, name: string, password: string) =>
    request<AuthState>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, name, password }),
    }),
  logout: () => request<{ detail: string }>("/auth/logout", { method: "POST" }),
  logoutAll: () => request<{ detail: string }>("/auth/logout-all", { method: "POST" }),
  me: () => request<AuthState>("/auth/me"),
  sessions: () => request<ActiveSession[]>("/auth/sessions"),
  revokeSession: (id: string) =>
    request<{ detail: string }>(`/auth/sessions/${id}`, { method: "DELETE" }),

  systemStatus: () => request<SystemStatus>("/system/status"),
  catalog: () => request<{ merchant: any; count: number; products: Product[] }>("/catalog"),

  shop: (query: string, opts?: { acceptBundle?: boolean; simulate?: string }) =>
    request<ShopResponse>("/buyer/shop", {
      method: "POST",
      body: JSON.stringify({
        query,
        accept_bundle: opts?.acceptBundle ?? false,
        simulate: opts?.simulate ?? null,
      }),
    }),
  buyerState: () => request<BuyerState>("/buyer/state"),
  updatePolicy: (patch: Record<string, unknown>) =>
    request<BuyerState["policy"]>("/buyer/policy", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),

  approvals: () => request<Approval[]>("/approvals"),
  // The deciding identity comes from the session server-side; there is no
  // actor field to send.
  decide: (id: string, decision: "approve" | "reject", note?: string) =>
    request<ShopResponse>(`/approvals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, note: note ?? null }),
    }),

  opportunities: () => request<Opportunity[]>("/merchant/opportunities"),
  decideOpportunity: (id: string, decision: "approve" | "reject") =>
    request<Opportunity>(`/merchant/opportunities/${id}/${decision}`, { method: "POST" }),
  merchantMetrics: () => request<any>("/merchant/metrics"),
  merchantTrust: () => request<TrustReport>("/merchant/trust"),

  auditEvents: (limit = 200) => request<AuditEvent[]>(`/audit/events?limit=${limit}`),
  auditTransactions: () => request<TransactionSummary[]>("/audit/transactions"),
  auditTimeline: (id: string) =>
    request<{ purchase_intent_id: string; event_count: number; events: AuditEvent[] }>(
      `/audit/timeline/${id}`,
    ),

  drill: (
    name: "policy-violation" | "payment-timeout" | "duplicate-webhook" | "tampered-webhook",
  ) => request<any>(`/drills/${name}`, { method: "POST" }),
};
