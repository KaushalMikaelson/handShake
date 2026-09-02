# Project Guide: handShake (Bounded AI-to-AI Commerce)

> **Track**: Razorpay AI Buildathon — Track 01  
> **Positioning**: *"A bounded AI commerce network where autonomous Buyer Agents can discover and purchase from AI-powered Merchant Agents while operating within explicit user policies, permissions, and human-approval controls."*

---

## 1. Executive Summary

**handShake** is a bounded AI-to-AI e-commerce platform. It enables a consumer's **Buyer Agent** to autonomously search, evaluate, negotiate bundles with, and purchase products from an AI-powered **Merchant Growth Agent** on Razorpay payment rails.

The core differentiator of handShake is **Bounded Autonomy**:
- **AI (LLM)** is used for natural language understanding, reasoning, product ranking, and business justifications.
- **Deterministic Python Code** handles all financial calculations, budget limits, permission checks, and payment executions.
- **The LLM has zero direct access to payment APIs or policy configurations.**

---

## 2. The Problem Statement

### 2.1 E-Commerce Assumption Breakdown
Traditional e-commerce assumes a human is browsing a visual UI, comparing products, and clicking checkout. As AI agents begin shopping on behalf of humans, two critical gaps emerge:
1. **Merchants aren't machine-readable**: Product catalogs are formatted for human eyes, not structured, machine-consumable endpoints for AI agents.
2. **Autonomous purchasing is all-or-nothing**: Either a human approves every single click (losing efficiency) or an agent holds a payment method with no guardrails (unacceptable financial risk).

### 2.2 Unbounded AI Risks
- **LLM Hallucinations**: An LLM might state a product costs ₹500 when the catalog price is ₹5,000, or invent a discount that burns merchant margin.
- **Runaway Spending**: Without hard boundaries, a compromised or prompt-injected LLM could drain a user's wallet.
- **Lack of Auditability**: Users need a clear, immutable record of *why* an agent made a financial decision.

---

## 3. Core Architecture & Security Principles

```
User (Natural Language Goal)
        │
        ▼
   BUYER AGENT (LLM: Intent parsing, candidate ranking, justification)
        │
        ▼  Emits PurchaseIntent (product_id, amount, merchant_id, reasoning)
   MERCHANT GROWTH AGENT (LLM: Proposes bundle/upsell or declines)
        │
        ▼  Emits Proposed Offer
   PERMISSION CHECK (Server-side capability verification)
        │
        ▼  Validates Allowed/Denied capabilities (e.g. REFUND_PAYMENT denied)
   DETERMINISTIC POLICY ENGINE (Pure Python — No LLM, No Network)
        │
        ├─► [BLOCKED] ──► Razorpay API is NEVER called (Logged & Terminated)
        ├─► [RECOMMEND_ONLY] ──► Level 1 Autonomy (No purchase allowed)
        ├─► [REQUIRES_APPROVAL] ─► Level 2/Threshold ──► HUMAN APPROVAL GATE
        └─► [AUTO_APPROVE] ────► Level 3 (< Threshold) ──► RAZORPAY PAYMENT
                                                                │
                                                                ▼
                                                    WEBHOOK HANDLER (Deduplicated)
                                                                │
                                                                ▼
                                                    IMMUTABLE AUDIT TRAIL
```

### The 7 Non-Negotiable Security Principles
1. **The LLM never directly controls money.**
2. **The LLM cannot modify spending policies.**
3. **The LLM cannot grant itself permissions.**
4. **Every financial operation is validated deterministically.**
5. **Every payment operation is fully auditable.**
6. **Unknown payment states must never trigger blind retries.**
7. **Hard financial limits override AI recommendations** — even for a maximally trusted merchant.

---

## 4. Key System Components

### 4.1 Agent-Readable Merchant Catalog
- Exposes structured JSON endpoints (`/catalog`) conforming to OpenAPI schemas.
- Contains SKUs with integer prices in **paise** (1 Rupee = 100 Paise), stock status, attributes, and discount ceilings (`max_discount_pct`).

### 4.2 Buyer Agent
- **Intent Parsing**: Converts natural language requests (e.g., *"Buy me wireless headphones under ₹10,000, prefer Sony"*) into structured intent. If no budget is specified, it sets `needs_clarification=True` and asks the user rather than guessing.
- **Candidate Evaluation**: Deterministically filters catalog products by category, stock, and budget constraints before invoking the LLM for ranking and plain-language justifications.
- **Authoritative Pricing**: Re-reads price directly from the database row by `product_id`, ignoring any price quoted in raw model output.

### 4.3 Merchant Growth Agent
- Evaluates anchor products to propose intelligent bundles (e.g., headphones + braided case) to increase Average Order Value (AOV).
- **Knowing When NOT to Use AI**: If no companion product is merchant-approved or affordable within the buyer's remaining budget, the agent explicitly returns `no_bundle_offered`.
- **Discount Ceiling**: Proposes discounts, but cannot exceed the merchant's `max_discount_pct` policy.

### 4.4 Deterministic Policy / Guardrail Engine
Implemented in pure, isolated Python with no network calls or LLM dependencies:
1. **Category Checks**: Ensures category is not in `blocked_categories` and is within `allowed_categories`.
2. **Per-Transaction Limit**: Ensures purchase amount $\le$ `max_transaction`.
3. **Rolling Budgets**: Checks daily (`spent_today + amount` $\le$ `daily_budget`) and monthly spend ledgers.
4. **Merchant Discount Cap**: Verifies proposed discount $\le$ `max_discount_pct`.
5. **Price Integrity**: Re-calculates discount arithmetic to prevent hallucinated discounts.

### 4.5 Autonomy Levels & Human Approval Gate
Buyers can configure three distinct levels of authority:
- **Level 1 (Recommend Only)**: Agent suggests products; cannot create executable purchase intents.
- **Level 2 (Prepare / Always Ask)**: Agent creates purchase intents, but every purchase requires human approval regardless of amount.
- **Level 3 (Bounded Auto-Purchase)**: Amounts below `allow_automatic_purchase_below` auto-execute if all policy checks pass; amounts $\ge$ `require_approval_above` route to the Human Approval Gate.

### 4.6 Permission System (Capability Checks)
- **Buyer Agent**: Granted `READ_PRODUCTS`, `SEARCH_PRODUCTS`, `COMPARE_PRODUCTS`, `CREATE_PURCHASE_INTENT`, `REQUEST_APPROVAL`, `CREATE_PAYMENT`. Explicitly denied `REFUND_PAYMENT`, `MODIFY_USER_POLICY`, `MODIFY_TRANSACTION_LIMIT`.
- **Merchant Agent**: Granted `PROPOSE_BUNDLE`. Denied `MODIFY_CATALOG_PRICING`, `CREATE_PAYMENT`.

### 4.7 Payment Execution & Failure Recovery
- **Razorpay Service**: Wraps order creation, capture, and status lookups. Supports both live Razorpay test-mode API keys and a local deterministic simulator.
- **Idempotency**: Derived from `purchase_intent_id`, ensuring retries never produce duplicate charges.
- **Webhook Signature Verification**: HMAC-SHA256 calculated over raw request bytes.
- **Webhook Deduplication**: Event IDs are claimed via DB-level `UNIQUE` constraints on `processed_webhook_events`. Replayed webhooks return `DUPLICATE_IGNORED`.

### 4.8 Immutable Audit Trail
- Logs every state transition (`USER_INTENT_RECEIVED`, `CATALOG_SEARCH`, `PRODUCT_SELECTED`, `OFFER_GENERATED`, `POLICY_CHECK`, `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, `RAZORPAY_ORDER_CREATED`, `ORDER_COMPLETED`, `POLICY_BLOCKED`, `PAYMENT_TIMEOUT`, `DUPLICATE_WEBHOOK`).
- Database table exposes no `UPDATE` or `DELETE` API paths.

### 4.9 Merchant Trust Engine (Advisory Only)
Calculates a 0–100 score based on 5 objective signals (verified catalog, completeness, pricing consistency, discount policy, fulfillment history). Trust is purely an advisory ranking signal and **can never override a policy rule**.

---

## 5. End-to-End Transaction Flow

```
1. USER input: "Buy wireless headphones under ₹10,000, prefer Sony"
2. BUYER AGENT parses intent -> {category: "electronics", budget_max: 1000000}
3. CATALOG search filters candidate SKUs deterministically
4. BUYER AGENT (LLM) selects Sony WH-CH720N (₹8,999) with reasoning
5. MERCHANT AGENT proposes approved companion bundle (AudioHub Case, 10% off)
6. PERMISSION CHECK verifies Buyer Agent holds CREATE_PURCHASE_INTENT
7. POLICY ENGINE evaluates 5 rules in fixed sequence -> ALL PASS
8. AUTONOMY ROUTING checks ₹8,999 >= ₹5,000 approval threshold -> REQUIRES_APPROVAL
9. HUMAN APPROVAL GATE displays full context -> User clicks APPROVE
10. PAYMENT EXECUTION creates Razorpay order with idempotency key
11. WEBHOOK HANDLER verifies HMAC signature, claims event ID, commits spend ledger
12. AUDIT TRAIL records timeline end-to-end
```

---

## 6. Failure Recovery Drills (US-10)

The system includes 4 interactive failure drills accessible on the Audit Trail dashboard:

| Drill | Scenario | System Behavior |
|---|---|---|
| **1. Policy Violation** | Spend exceeds policy limit | Engine returns `BLOCKED`, names exact failed rule, asserts Razorpay API was zero-called |
| **2. Payment Timeout** | Network times out during order creation | State set to `PENDING_VERIFICATION`. System fetches order status by receipt from gateway — **never blindly retries** |
| **3. Duplicate Webhook** | Webhook payload delivered twice | Second delivery hits DB unique constraint, logged as `DUPLICATE_IGNORED`, spend committed exactly once |
| **4. Forged Signature** | Webhook arrives with invalid HMAC | Rejected immediately before body parsing or database insertion |

---

## 7. Tech Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, SQLite/PostgreSQL, Pytest (169 unit & integration tests)
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons
- **Payments**: Razorpay Python SDK (Test Mode) + Built-in Local Simulator
- **AI Integration**: Anthropic Claude Structured Outputs + Rule-Based Deterministic Fallback Mode
