# handShake — User Guide

How to run the app, what each screen does, and how to walk through the whole
story in five minutes.

---

## 1. Start it

Nothing to configure. Razorpay and the LLM both fall back to deterministic
local implementations when credentials are absent, so the full system — every
screen, every failure drill — runs with no third-party accounts.

```bash
# Option A — Docker (Postgres + API + frontend)
docker compose up --build

# Option B — local, no Docker
./scripts/dev.sh
```

| What | Where |
|---|---|
| The app | http://localhost:5173 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| Which mode it's running in | http://localhost:8000/system/status |

Verify it works: `./scripts/test.sh` (169 backend tests + frontend build).

---

## 2. Sign in

Three demo accounts are on the login screen — click one to fill the form, then
**Sign in**. Password for all three: `Demo@1234`

| Account | Role | Sees |
|---|---|---|
| `aditi@handshake.demo` | Buyer | Buyer · Approvals · Audit Trail |
| `merchant@audiohub.demo` | Merchant | Merchant · Audit Trail |
| `admin@handshake.demo` | Admin | Everything (read/observe only) |

**Start with the buyer account** — it drives the main story.

You can also create your own account with **Create one**. New accounts start
deliberately locked down: a ₹3,000 per-transaction cap and *ask me every time*.
You widen those yourself from the Buyer screen.

> **Admin is not a superuser.** It can view both dashboards, but it holds no
> financial authority whatsoever — an admin attempting an over-limit purchase
> is blocked by exactly the same rule as anyone else. This is enforced, not
> promised: see `test_admin_role_cannot_bypass_the_policy_engine`.

**Signing out** — click your name at the bottom of the sidebar → **Sign out**.
The session is revoked on the server, so the cookie is dead immediately, not
whenever it would have expired.

---

## 3. The screens

### Buyer — where the agent works

The left rail is your control panel:

- **Autonomy level** — how much authority you've delegated. Click to change it.
  - *Recommend only* — the agent suggests, never buys
  - *Always ask me* — every purchase needs your approval, whatever the amount
  - *Bounded auto-buy* — small amounts go through alone, within all limits
- **Budgets** — daily and monthly, showing what's spent and what's left. These
  only move when money actually moves; a blocked or rejected attempt costs you
  nothing.
- **Active policy** — the hard limits. The agent cannot exceed these.
- **Agent permissions** — what the agent may do (green) and may never do (red).
  The red list is fixed in code; no model output can extend it.

The main column is where you shop. Type a goal in plain language and press
**Run buyer agent** (or `⌘/Ctrl + Enter`). Four scripted prompts are provided so
each outcome triggers reliably.

**What comes back, in order:**

1. **Outcome** — what happened, and whether Razorpay was called at all
2. **Agent recommendation** — the pick, why, and *every* candidate it
   considered, with a specific reason for each rejection ("Exceeds budget by
   ₹1,999")
3. **Merchant growth agent** — a bundle offer, or an explicit
   `no_bundle_offered` with a reason
4. **Policy engine verdict** — every rule, in evaluation order, pass or fail
5. **Approval** — if the amount needs you
6. **Transaction** — the Razorpay order, once paid
7. **Merchant trust** — an advisory score that cannot override any rule

### Approvals — the human gate

Purchases the agent prepared but may not execute alone. Each shows the amount,
your remaining budget after it, the agent's reasoning, and an expandable policy
report.

**Approve** or **Reject** — those are the only two options. Rejecting asks you
to confirm, then ends the flow and charges nothing. There is no
approve-on-timeout: an untouched request stays pending forever, which is the
safe default.

Decisions are attributed to your real signed-in identity, and the history table
shows who decided what.

### Merchant — the growth side

Revenue, order count, AOV, and how many purchases the *buyer's* policy stopped.

**Growth opportunities** are product pairings the merchant agent may offer.
Reject one and it's removed from the agent's options immediately — the agent
can only bundle what a human approved, and it never writes catalog pricing
itself.

### Audit Trail — the whole story

The screen that proves the rest. Pick a transaction on the left; its full
ordered timeline appears on the right. Expand any event for the raw inputs,
outputs and policy verdict.

A successful purchase produces about twelve events, from
`USER_INTENT_RECEIVED` through `ORDER_COMPLETED`. Every one carries a
timestamp, the acting agent, and a plain-language reason.

**Failure-mode drills** are the four buttons at the top. Each runs the same
production code path a real failure would take:

| Drill | What you should see |
|---|---|
| Policy violation | `BLOCKED`, the exact rule named, `razorpay_called: false` |
| Payment timeout | `PENDING_VERIFICATION`, then resolution by *asking* the gateway — never a blind retry |
| Duplicate webhook | First delivery processed, second `duplicate_ignored`, spend counted once |
| Forged signature | Rejected before the payload is even parsed |

> The duplicate-webhook drill needs a *paid* transaction to replay. Run the
> auto-purchase prompt first, or it will tell you so.

---

## 4. The five-minute walkthrough

Sign in as **aditi@handshake.demo** and work down the scripted prompts.

**① Auto-purchase** — "a braided aux cable, budget ₹1,000"
₹299 passes every rule and sits below your ₹2,000 auto-buy threshold, so the
agent pays without asking. Note the merchant agent *declining* to bundle: there
is no sensible companion for a cable, and it says so rather than forcing an
upsell.

**② Approval gate** — "wireless headphones under ₹10,000, prefer Sony"
₹8,999 is above your ₹5,000 threshold, so it stops and asks. Check
`razorpay_called: false`, read the seven-rule policy report, then **Approve**
and watch it pay.

**③ Blocked** — "premium Sennheiser, budget up to ₹20,000"
₹11,999 exceeds your ₹10,000 cap. Blocked, with `budget.max_transaction` named
— and the merchant still scores 100/100 trust. **Trust never overrides budget.**

**④ Needs clarification** — "some good headphones"
No budget stated, so the agent asks instead of inventing one.

**⑤ Failure recovery** — Audit Trail → run all four drills.

**⑥ Close on the audit trail** — pick the completed purchase and show the
timeline end to end.

The same sequence runs headless if you'd rather not click:

```bash
python scripts/demo.py
```

---

## 5. Switching on the real integrations

Copy `.env.example` to `.env` and fill in what you have. Everything is
optional; anything you leave blank keeps its local fallback.

```bash
RAZORPAY_KEY_ID=rzp_test_xxxxx        # TEST MODE ONLY
RAZORPAY_KEY_SECRET=xxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxx         # must match the dashboard webhook
ANTHROPIC_API_KEY=sk-ant-xxxxx        # agents use the LLM path instead of rules
```

Restart, then check `/system/status` — it always reports which mode is live, so
a demo can never quietly overclaim.

For webhooks in local development, expose the API with a tunnel
(`ngrok http 8000`) and point the Razorpay dashboard webhook at
`https://<your-tunnel>/webhooks/razorpay`.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Login says "Invalid email or password" | Password is `Demo@1234` (capital D, `@`). The same message appears for a wrong password *and* an unknown account — that's deliberate, so nobody can probe which emails exist. |
| "Too many failed attempts" | Five wrong passwords locks an account for 15 minutes. Use a different demo account, or restart the API with a fresh database. |
| Bounced to the login screen mid-session | Your session expired (12h) or was revoked elsewhere. Sign in again. |
| Merchant screen 403s | You're signed in as the buyer. Roles are enforced server-side — sign in as the merchant account. |
| Approvals list is empty | Approvals are per-buyer. You only ever see your own. |
| Duplicate-webhook drill fails | It needs a paid transaction. Run the auto-purchase prompt first. |
| Payments pill says `simulator` | No Razorpay credentials configured. Expected, and everything still works. |
| Agents pill says `deterministic` | No `ANTHROPIC_API_KEY`. The agents use their rule-based path; every guardrail behaves identically. |
| Port 8000 or 5173 already in use | An older server is still running. Kill it, or change the port. |
| Frontend shows a PostCSS error | A stale dev server. Stop it, `rm -rf frontend/node_modules/.vite`, restart. |

---

## 7. Where things live

```
backend/app/
  policies/      the deterministic engine — no LLM, no network, no DB
  agents/        the only LLM-touching code
  payments/      the only module that imports the Razorpay SDK
  services/      orchestrator · auth · audit · ledger · security
frontend/src/
  pages/         Login · Buyer · Approvals · Merchant · Audit
tests/           169 tests
docs/            architecture.md · safety.md · agent-protocol.md
```

Further reading: [`architecture.md`](architecture.md) for how it fits together,
[`safety.md`](safety.md) for the security model and threat table, and
[`agent-protocol.md`](agent-protocol.md) for the wire contract another agent
would code against.

---

*A rendered, shareable version of this guide is published at
<https://claude.ai/code/artifact/feeb7c69-0661-464f-9541-9e3bcd8362ee>.*
