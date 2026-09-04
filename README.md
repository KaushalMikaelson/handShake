# Bounded AI-to-AI Commerce

**Buyer Agent × Merchant Growth Agent, on Razorpay rails, with deterministic financial controls.**

Razorpay AI Buildathon — Track 01

> A bounded AI commerce network where autonomous Buyer Agents discover and
> purchase from AI-powered Merchant Agents while operating within explicit user
> policies, permissions, and human-approval controls.

The differentiator is not autonomy. It's **controlled autonomy** for financial
transactions.

---

## The one-sentence version

> We didn't build an AI that can spend money — we built an AI that can spend
> money only within rules its owner controls.

---

## Quick start

No Razorpay account, no Anthropic key, no configuration. Both integrations fall
back to deterministic local implementations when credentials are absent, and
**every guardrail behaves identically either way**.

```bash
# Option A — Docker (Postgres + API + frontend)
docker compose up --build

# Option B — local
.\scripts\dev.ps1
```

| | |
|---|---|
| Frontend | http://localhost:5173 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| Integration mode | http://localhost:8000/system/status |

**Sign in** with a demo account (all use password `Demo@1234`):

| Account | Role | Sees |
|---|---|---|
| `aditi@handshake.demo` | Buyer | Buyer · Approvals · Audit — **start here** |
| `merchant@audiohub.demo` | Merchant | Merchant · Audit |
| `admin@handshake.demo` | Admin | Everything — and still no financial authority |

New to the app? Read the [**User Guide**](docs/USER_GUIDE.md).

```bash
.\scripts\test.ps1              # 128 backend tests + frontend typecheck & build
python scripts\demo.py         # drives the full 5-minute demo end to end
```

To use the real gateway, copy `.env.example` to `.env` and add Razorpay
**test-mode** keys. The same code path then talks to Razorpay.

---

## The architectural rule

**The LLM has no tool, function, or route that reaches the payment gateway.**

The only interfaces between the AI layer and money are the permission check and
the policy engine — both plain Python, no model in the loop.

```
User (natural language)
      │
      ▼
BUYER AGENT ─────────────► LLM ranks and explains
      │  emits PurchaseIntent — a request, never an executable action
      ▼
MERCHANT GROWTH AGENT ───► LLM proposes a bundle, or declines
      │  emits an offer — still unauthorized
      ▼
PERMISSION CHECK ────────► deterministic
      ▼
POLICY ENGINE ───────────► deterministic · no LLM · no network · no DB
      │
      ├── PASS + below auto threshold ──► proceed autonomously
      ├── PASS + at/above threshold ────► HUMAN APPROVAL GATE
      └── FAIL ─────────────────────────► BLOCKED · Razorpay never called
      ▼
RAZORPAY TEST MODE ──────► idempotency key, signature verification
      ▼
AUDIT LOG ───────────────► append-only, timestamped, every step
```

A prompt injection that fully hijacks the model still cannot issue a refund,
raise a limit, or move money. It can only produce a differently-worded
*proposal*, which the deterministic layers then reject.

This is enforced three independent ways so it cannot decay: no payment tool is
ever defined for the model; an import-boundary test fails the build if an agent
module reaches the payment layer; and the chargeable amount is always re-read
from the catalog by `product_id`.

---

## What's built

### Authentication & identity
- **Real login/logout** — bcrypt passwords, opaque server-side sessions in
  `httpOnly` `SameSite=Strict` cookies, and logout that *revokes the session
  server-side* rather than just dropping a cookie.
- **Role-gated access** — buyer, merchant and admin see different screens, and
  the server decides which, not the client.
- **Ownership on approvals** — a purchase can only be decided by the buyer whose
  money it is. Before auth existed, any caller could approve anything.
- **Attributable decisions** — the audit trail records the verified session
  identity. The `actor` field was removed from the API rather than left as a
  claim to be trusted (this is what US-12 actually asked for).
- **Authentication is not authorization** — no role, including admin, can raise
  a limit or unblock a purchase. `evaluate()` has nowhere to *put* an identity.

### Safety & control
- **Deterministic policy engine** — category → per-transaction → daily → monthly
  → bundle discount, evaluated in that order. First failure names the rule.
  Zero LLM, network or ORM imports, verified per-file by a test.
- **Permission system** — fixed capability sets as immutable constants. Denial is
  explicit and wins over allow. Unknown agents hold nothing.
- **Three autonomy levels** — L1 recommend only · L2 always ask · L3 bounded
  auto-purchase below a threshold.
- **Human approval gate** — explicit Approve/Reject with full context. No
  timeout-to-approve path exists.
- **Trust engine** — advisory ranking signal that is *not a parameter of the
  policy engine*. A 100/100 merchant over the limit is still blocked.

### Payments
- Single-module Razorpay ownership; nothing else imports the SDK.
- Idempotency keys derived from `purchase_intent_id` — retrying an intent can
  never create a second order.
- Webhook signature verified over the **raw body**, before parsing.
- Replay protection via a DB-unique `event_id`, not an application-level check.

### Audit
- Append-only, immutable; no UPDATE/DELETE path exists and the API is GET-only.
- Every event carries a timestamp, the acting agent, the reasoning and the
  policy verdict.
- The whole flow lands on one timeline — the intent id is allocated before the
  agents run precisely so the reasoning that led to a decision is not orphaned.

### Failure handling (all four demonstrable on demand)
| Drill | Behaviour |
|---|---|
| Policy violation | BLOCKED, rule named, **zero** calls on the payment client |
| Payment timeout | `PENDING_VERIFICATION` → ask the gateway → reconcile. Never a blind retry |
| Duplicate webhook | Second delivery ignored; spend committed exactly once |
| Forged signature | Rejected before the body is parsed |

### Interface
Login plus four role-gated dashboards: buyer (agent state, budgets, autonomy, NL
input), approvals, merchant (opportunities, metrics, trust), and an audit
timeline with the failure drills wired in as buttons.

Light and dark themes, toast feedback on every action, loading skeletons,
confirmation on destructive actions, a live pending-approval badge, keyboard
focus rings throughout, and a responsive layout down to mobile.

---

## Tested

```
169 passed
```

| Suite | Covers |
|---|---|
| `test_policy_engine.py` (25) | Every rule, boundary and autonomy level — no mocks, no fixtures |
| `test_agents.py` (23) | Parsing, ranking, rejection reasons, bundle decline |
| `test_api.py` (24) | Full HTTP surface including validation and conflict handling |
| `test_auth.py` (41) | Hashing, sessions, revocation, roles, ownership, lockout |
| `test_money.py` (18) | Paise integrity from catalog row to Razorpay order |
| `test_architecture.py` (13) | Import boundaries, tool schemas, audit immutability |
| `test_trust_and_permissions.py` (13) | Capability enforcement; trust cannot override policy |
| `test_failure_modes.py` (12) | The scored failure paths, asserting the *mechanism* |

The architecture tests are the interesting ones: they turn claims in this README
into build failures if the code ever contradicts them.

The suite runs on SQLite by default (with `PRAGMA foreign_keys=ON`, since SQLite
otherwise ignores them) and against the real deployment database on demand:

```bash
TEST_DATABASE_URL=postgresql+psycopg2://agent:agent@127.0.0.1:5432/agent_commerce_test \
  backend/.venv/bin/python -m pytest tests
```

That path matters — the duplicate-webhook and idempotency guarantees rest on DB
constraints, so they are worth verifying on Postgres and not just on SQLite.
All 128 pass on both.

---

## AI judgment: what we deliberately did *not* build

Sequencing was the hard part of this brief, not implementation. Each of these
solves a real problem — at a scale this system does not operate at — and each is
a live-demo failure surface with no corresponding benefit.

| Not built | Why it's right eventually | Why not now |
|---|---|---|
| **Vector search / RAG** over the catalog | Semantic retrieval across a large catalog | 3–5 SKUs. SQL filtering is strictly sufficient; embeddings here are pure scope risk |
| **LangGraph** | Branching, stateful multi-agent workflows | This flow is a linear pipeline. Wrapping straight-line calls buys abstraction we'd never use |
| **Redis** | Distributed session/cache state | Single instance. The Postgres uniqueness constraint already does this job — better, because it's transactional |
| **Clerk / hosted auth** | Multi-tenant production identity, SSO, MFA | Auth is now built in directly — sessions, roles and ownership — without a third-party dependency or a live-demo failure surface. Email verification, password reset and MFA remain out of scope |
| **Sentry** | Production error monitoring | No live user base during judging |
| **Kubernetes** | Multi-node orchestration | One container |
| **Multi-round negotiation** | Richer price discovery | Single request → single offer keeps the safety gate legible |
| **Live ML trust scoring** | Real reputation at scale | Rule-derived score is honest about what it is and cannot mislead |

The same judgment shows up in the product: the merchant agent returns
`no_bundle_offered` **with a reason** when nothing fits. Forcing an upsell onto
every transaction would have been easier to demo and worse.

---

## Repository layout

```
backend/app/
  agents/           buyer/ merchant/ llm/     ← the only LLM-touching code
  policies/         budget · category · permission · approval · engine
  payments/         razorpay_service.py · webhook.py
  trust/            advisory scoring
  services/         orchestrator · audit · ledger · money · seed
  api/routes/       catalog · buyer · approvals · merchant · audit · webhooks · drills
frontend/src/
  pages/            BuyerPage · ApprovalsPage · MerchantPage · AuditPage
tests/              128 tests
docs/               architecture.md · agent-protocol.md · safety.md
scripts/            dev.sh · test.sh · demo.py
```

---

## Resolved design questions

| Question | Decision |
|---|---|
| Rupees or paise? | **Integer paise everywhere.** One conversion boundary, in the UI formatter |
| One service or two? | **One service, two logical modules.** v2 would split them |
| Where does spend live? | **Persisted in Postgres.** Survives restart; a new session cannot reset a limit |
| Scripted or live demo input? | **Scripted prompts, live input also available** — failure beats must trigger reliably |
| Build the trust engine? | **Yes**, after P0 was complete — and wired so it provably cannot override policy |
| Auth: hosted or built? | **Built in**, once it was explicitly requested. Kept strictly separate from authorization so it could not weaken the policy engine |

---

## Docs

- [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) — **how to run and use the app**, screen by screen, with a five-minute walkthrough
- [`docs/architecture.md`](docs/architecture.md) — component boundaries, data model, why plain Python
- [`docs/safety.md`](docs/safety.md) — the seven principles, threat model, and what is *not* protected
- [`docs/agent-protocol.md`](docs/agent-protocol.md) — the wire contract for a consuming agent
