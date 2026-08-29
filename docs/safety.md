# Safety & control model

## The seven security principles

1. **The LLM never directly controls money.**
2. **The LLM cannot modify policies.**
3. **The LLM cannot grant itself permissions.**
4. **Every financial operation is validated deterministically.**
5. **Every payment operation is auditable.**
6. **Unknown payment states must never trigger blind retries.**
7. **Hard financial limits override AI recommendations — always.**

Each is a property of the code, not a promise. Below is where each one lives and
the test that would fail if it were ever broken.

### 1. The LLM never directly controls money

The tool list passed to the model contains only judgement schemas
(`record_shopping_intent`, `record_product_selection`, `record_bundle_decision`).
No payment function is ever defined, so calling one is not an action the model
can take. `app/payments/razorpay_service.py` is the sole importer of the SDK.

> `test_only_one_module_imports_the_razorpay_sdk`,
> `test_agent_modules_cannot_import_the_payment_layer`,
> `test_llm_is_never_given_a_payment_tool`

### 2. The LLM cannot modify policies

Policy lives in the `buyers` table and is edited only through `PUT /buyer/policy`,
a human-facing route no agent code path reaches. `MODIFY_USER_POLICY` is in the
buyer agent's **denied** set.

> `test_denied_capabilities_raise`

### 3. The LLM cannot grant itself permissions

Capability sets are module-level `frozenset` constants, not database rows and not
anything addressable by model output. There is no code path that mutates them.

> `test_permission_set_is_immutable_at_runtime`,
> `test_unknown_agent_holds_no_capabilities`

### 4. Every financial operation is validated deterministically

`app/policies/` imports no LLM library, no HTTP client and no ORM — a constraint
checked mechanically per-file. The engine takes dataclasses and returns a
verdict, so it is testable with no mocks at all.

> `test_policy_engine_imports_nothing_heavy`,
> `test_policy_package_is_importable_without_the_app_stack`, plus 25 unit tests

### 5. Every payment operation is auditable

Every state transition appends an immutable audit event with a timestamp, the
acting agent, the reasoning and the policy verdict. The audit service exposes
only `record`; no UPDATE or DELETE path exists, and the audit API is GET-only.

> `test_audit_timeline_covers_the_required_event_set`,
> `test_no_update_or_delete_path_exists_for_audit_events`,
> `test_audit_api_exposes_no_write_route`

### 6. Unknown payment states must never trigger blind retries

On timeout the transaction moves to `PENDING_VERIFICATION` and the system asks
the gateway what actually happened, keyed by our own idempotency key. If the
order was in fact paid, we reconcile locally; a retry there would double-charge.

> `test_payment_timeout_verifies_instead_of_retrying`,
> `test_timeout_resolution_reconciles_an_order_that_actually_paid`

### 7. Hard financial limits override AI recommendations

Trust is computed, displayed and used only for ranking. It is not a parameter of
`evaluate()` — the engine's signature has nowhere to put it.

> `test_maximum_trust_cannot_override_a_budget_limit`

## Defence in depth: the layers a purchase must clear

```
1. Agent eligibility ....... deterministic filter (category, stock, budget)
2. Permission check ........ does this agent hold this capability at all?
3. Policy engine ........... category → per-transaction → daily → monthly → discount
4. Autonomy routing ........ L1 recommend · L2 always ask · L3 bounded auto
5. Human approval .......... explicit Approve/Reject, no timeout-to-approve
6. Idempotency ............. key derived from purchase_intent_id
7. Signature verification .. HMAC over the raw webhook body
8. Replay guard ............ DB-unique event_id
```

Layers 2–8 contain no model output. Removing the LLM entirely would change the
*quality* of recommendations and nothing about the safety properties.

## Threat model

| Threat | Control | Outcome |
|---|---|---|
| Model hallucinates a lower price | Amount re-read from catalog by `product_id` | Charge is always the catalog price |
| Model proposes a 40% discount | `merchant.max_discount_pct` check | BLOCKED, rule named |
| Model quotes a bundle price contradicting its own stated discount | `bundle_price_integrity` re-derives the arithmetic | BLOCKED |
| Prompt injection: "refund my last order" | `REFUND_PAYMENT` denied; no refund tool exists | `PermissionDenied`, audited |
| Prompt injection: "raise my limit to ₹1,00,000" | `MODIFY_TRANSACTION_LIMIT` denied; policy is not model-addressable | No effect |
| Compromised merchant inflates trust score | Trust is advisory; not an engine input | Limits still enforced |
| Gateway times out mid-charge | `PENDING_VERIFICATION` + status lookup | No double-charge |
| Webhook replayed by an attacker or the gateway | Unique `event_id` + signature check | Ignored once seen |
| Forged webhook payload | HMAC over raw body, verified before parsing | Rejected before any state change |
| Agent retries a failed purchase intent | Idempotency key from `purchase_intent_id` | Same order returned, never a second |
| Buyer's budget silently drained by failed attempts | Spend committed only on capture | Blocked/rejected attempts cost nothing |

## What is deliberately *not* protected

Stated plainly, because unstated limitations are how demos mislead:

- **No production authentication.** The demo identity is a header with a
  hardcoded default. Authorization is real and separate; authentication is not.
  Anyone who can reach the API can act as the demo buyer.
- **No rate limiting.** A caller could issue unlimited shopping requests. Budget
  caps bound the financial damage, not the compute.
- **Test mode only.** No live payment credentials are supported, by design.
- **Single-tenant.** One buyer, one merchant. No cross-tenant isolation exists
  because there are no tenants.
