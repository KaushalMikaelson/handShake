# Architecture

## The one rule everything else serves

**The LLM has no tool, function, or route that reaches the payment gateway.**

The only interfaces between the AI layer and money are the permission check and
the policy engine — both plain Python, no model in the loop. This is enforced in
three independent ways, so it cannot decay:

| Enforcement | Where | What it prevents |
|---|---|---|
| No payment tool is ever defined | `agents/llm/client.py` — the tool list contains only judgement schemas | The model cannot *call* a payment function, because none exists in its action space |
| Import boundary | `tests/test_architecture.py` | Any future agent module that imports `app.payments` fails the build |
| Amount re-derivation | `orchestrator.py` reads `Product.price` by `product_id` | A hallucinated price cannot become a charge |

A prompt injection that fully hijacks the model still cannot issue a refund,
raise a limit, or move money. It can only produce a differently-worded
*proposal*, which the deterministic layers then reject.

## Request flow

```
User (natural language)
      │
      ▼
BUYER AGENT ................... LLM: intent parsing, ranking, justification
      │  emits PurchaseIntent {product_id, amount, merchant_id, reasoning}
      │  ── a request, never an executable action
      ▼
MERCHANT GROWTH AGENT ......... LLM: bundle proposal, or "no_bundle_offered"
      │  emits an offer — still unauthorized
      ▼
PERMISSION CHECK .............. deterministic: does this agent hold this capability?
      ▼
POLICY / GUARDRAIL ENGINE ..... deterministic: no LLM, no network, no DB
      │
      ├── PASS + below auto threshold ──► proceed (Level 3 autonomy)
      ├── PASS + at/above threshold ────► HUMAN APPROVAL GATE (Level 2)
      └── FAIL ─────────────────────────► BLOCKED · Razorpay never called
      ▼
TRUST ENGINE .................. advisory ranking signal only, cannot override policy
      ▼
RAZORPAY TEST MODE ............ order creation with an idempotency key, capture
      ▼
WEBHOOK HANDLER ............... signature verified, event_id deduplicated
      ▼
AUDIT LOG ..................... append-only, timestamped, every step
```

Read `services/orchestrator.py` top to bottom and this flow is the control flow:
the agents run first and produce only proposals, the two gates sit between them
and `execute_payment`, and there is exactly one call site for order creation.

## Why plain Python instead of LangGraph

The flow above is a **linear pipeline**, not a graph with meaningful branches.
LangGraph earns its keep on stateful multi-agent workflows with loops, retries
and checkpoints; wrapping a straight-line sequence of function calls in it would
add a dependency, a learning curve and a runtime failure surface to buy
abstraction we would not use. The decision was made once, on day one, and not
revisited.

## Money representation

**Integer paise, everywhere.** Razorpay's API expects paise, so storing rupees
anywhere would create a conversion point — and a 100× bug waiting to happen.

There is exactly one conversion boundary in the entire system:
`frontend/src/services/format.ts`. Nothing server-side ever handles rupees, and
no monetary value is ever a float. `tests/test_money.py` asserts this at every
hop from catalog row to Razorpay order.

## Component boundaries

| Component | Deterministic? | May call the LLM? | May call Razorpay? |
|---|---|---|---|
| `agents/buyer` | partly | **yes** | no |
| `agents/merchant` | partly | **yes** | no |
| `policies/` | **fully** | no | no |
| `trust/` | **fully** | no | no |
| `payments/razorpay_service.py` | **fully** | no | **yes — sole owner** |
| `services/audit.py` | **fully** | no | no |

`policies/` imports nothing but the standard library and a formatting helper.
That is why the component guarding money is the easiest one in the system to
test: 25 unit tests, zero mocks, zero fixtures.

## Running without credentials

Both third-party dependencies degrade to a deterministic local implementation
when their keys are absent, so the full system — including all four failure
drills — runs with no accounts:

- **No `RAZORPAY_KEY_ID`** → an in-process simulator with identical method
  signatures, return shapes, idempotency behaviour and HMAC signature
  semantics. Set real test-mode keys and the *same code path* talks to Razorpay.
- **No `ANTHROPIC_API_KEY`** → the agents use their rule-based path: keyword and
  magnitude-aware intent parsing, deterministic scoring, templated
  justifications.

**Every guardrail behaves identically in both modes.** The policy engine, the
permission system, idempotency, signature verification and the audit trail have
no dependency on either service. `/system/status` always reports which mode is
active, so a demo can never accidentally overclaim.

## Data model

| Table | Purpose | Notable constraint |
|---|---|---|
| `products` | agent-readable catalog | `price` integer paise |
| `buyers` | identity + policy config | policy is data, not code |
| `spend_ledger` | committed spend | written only on capture |
| `purchase_intents` | agent proposals | carries reasoning + policy verdict |
| `approval_requests` | human gate | no timeout-to-approve path |
| `transactions` | payment records | **unique** `idempotency_key` |
| `audit_events` | append-only trail | no UPDATE/DELETE path exists |
| `processed_webhook_events` | replay guard | **unique** `event_id` |

The two uniqueness constraints do real work. `idempotency_key` makes retrying a
purchase intent incapable of creating a second order. `event_id` is what makes
duplicate webhook handling correct: concurrent deliveries race on the INSERT and
exactly one wins, rather than both passing an `if already_seen` check.

## What v2 would add, and why not now

| Deferred | Why it's right eventually | Why not now |
|---|---|---|
| Redis | Distributed session/cache state | Single instance; Postgres constraints already do this job |
| pgvector / RAG | Semantic search over a large catalog | 3–5 SKUs — SQL filtering is strictly sufficient |
| Clerk | Multi-tenant production auth | One demo buyer, one demo merchant; authorization is already separate |
| Sentry | Production error monitoring | No live user base during judging |
| Kubernetes | Multi-node orchestration | One container |
| Separate agent services | Independent scaling/deploy | Two logical modules in one service is the right size today |
| Multi-round negotiation | Richer price discovery | Single request → single offer keeps the gate legible |

Each solves a real problem at a scale this system does not operate at, and each
is a live-demo failure surface with no corresponding benefit here.
