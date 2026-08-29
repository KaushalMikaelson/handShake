/** Typed client for the backend. Mirrors the FastAPI OpenAPI contract. */

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 300)}`);
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

export interface SystemStatus {
  environment: string;
  payments: { mode: string; live: boolean; note: string; calls_made: number };
  llm: { mode: string; live: boolean; model: string | null; note: string };
  permissions: Record<string, { allowed: string[]; denied: string[] }>;
  security_principles: string[];
}

// ---------- endpoints ----------
export const api = {
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
  decide: (id: string, decision: "approve" | "reject", note?: string) =>
    request<ShopResponse>(`/approvals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, actor: "aditi", note: note ?? null }),
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
