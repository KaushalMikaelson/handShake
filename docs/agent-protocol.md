# Agent protocol

How an autonomous buyer agent transacts with this merchant. Every payload below
is a Pydantic model on the server, published as OpenAPI at `/openapi.json`, so
an agent codes against a contract rather than scraping a page.

## 1. Discover the catalog

```http
GET /catalog?category=electronics&max_price=1000000&in_stock_only=true
```

```json
{
  "merchant": { "id": "merchant_audiohub", "max_discount_pct": 10 },
  "currency": "INR",
  "amount_unit": "paise",
  "count": 3,
  "products": [
    {
      "product_id": "prod_sony_whch720n",
      "name": "Sony WH-CH720N Wireless Noise Cancelling Headphones",
      "brand": "Sony",
      "price": 899900,
      "currency": "INR",
      "category": "electronics",
      "stock_available": true,
      "attributes": ["wireless", "noise-cancelling", "over-ear", "35h-battery"],
      "bundle_eligible": true,
      "max_discount_pct": 10
    }
  ]
}
```

`price` is **integer paise**. `amount_unit` is stated explicitly in every
response so a consuming agent never has to infer it.

## 2. Submit a shopping goal

```http
POST /buyer/shop
{
  "query": "Buy me wireless headphones under ₹10,000, prefer Sony",
  "accept_bundle": false,
  "simulate": null
}
```

The response is the complete record of one run: parsed intent, per-candidate
evaluation, the merchant's bundle decision, the trust report, the per-rule policy
verdict, and whichever of `approval` / `transaction` applies.

### Terminal statuses

| `status` | Meaning | Next step |
|---|---|---|
| `completed` | Paid under Level 3 autonomy | none |
| `awaiting_approval` | Above threshold | `POST /approvals/{id}/decision` |
| `blocked` | Failed a policy rule — `policy.failed_rule` names it | adjust or abandon |
| `needs_clarification` | No budget was stated | ask the user, resubmit |
| `no_match` | Nothing in the catalog fits | none |
| `recommendation_only` | Level 1 autonomy | none |
| `pending_verification` | Payment state unresolved | poll the audit timeline |
| `rejected` | Human declined | none |

`razorpay_called` is present on every response, so a client can verify for itself
that a blocked purchase never reached the gateway.

## 3. The PurchaseIntent contract

`PurchaseIntent` is the **only** interface between the AI layer and the rest of
the system. It is a request, not an executable action — nothing about holding one
grants the ability to move money.

```json
{
  "intent_id": "pi_9e8e034f02b84e34",
  "buyer_id": "buyer_aditi",
  "merchant_id": "merchant_audiohub",
  "product_id": "prod_sony_whch720n",
  "amount": 899900,
  "currency": "INR",
  "reasoning": "Selected Sony WH-CH720N at ₹8,999; matches your preferred brand…",
  "status": "AWAITING_APPROVAL"
}
```

`amount` is authoritative and always re-read from the catalog by `product_id`.
It is never taken from model output.

## 4. Resolve a human approval

```http
POST /approvals/{approval_id}/decision
{ "decision": "approve", "actor": "aditi", "note": "looks right" }
```

Only `approve` and `reject` are accepted. A decided approval returns **409** if
decided again, so a double-submit cannot become a second charge.

## 5. Webhooks

```http
POST /webhooks/razorpay
X-Razorpay-Signature: <hmac-sha256 of the raw body>
X-Razorpay-Event-Id: <event id>
```

- The signature is verified over the **raw bytes**, before the body is parsed.
- `event_id` is claimed via an INSERT against a unique constraint.
- Duplicates return **200** with `"status": "duplicate_ignored"` — a duplicate is
  a successfully handled delivery, and erroring would invite endless retries.

## 6. Read the audit trail

```http
GET /audit/timeline/{purchase_intent_id}
```

Returns the full ordered history. A successful purchase produces at least:

```
USER_INTENT_RECEIVED → CATALOG_SEARCH → PRODUCT_SELECTED
→ OFFER_GENERATED | NO_BUNDLE_OFFERED → TRUST_EVALUATED
→ PERMISSION_CHECK → POLICY_CHECK → [APPROVAL_REQUESTED → APPROVAL_GRANTED]
→ RAZORPAY_ORDER_CREATED → PAYMENT_CONFIRMED → ORDER_COMPLETED → WEBHOOK_PROCESSED
```

Failure paths add `POLICY_BLOCKED`, `PERMISSION_DENIED`, `PAYMENT_TIMEOUT`,
`PAYMENT_STATE_RESOLVED`, `DUPLICATE_WEBHOOK`, `WEBHOOK_SIGNATURE_INVALID`
or `INVALID_REQUEST`.

## 7. Agent capabilities

```
buyer_agent
  ALLOWED  READ_PRODUCTS · SEARCH_PRODUCTS · COMPARE_PRODUCTS
           CREATE_PURCHASE_INTENT · REQUEST_APPROVAL · CREATE_PAYMENT
  DENIED   REFUND_PAYMENT · MODIFY_USER_POLICY · MODIFY_TRANSACTION_LIMIT

merchant_agent
  ALLOWED  READ_PRODUCTS · READ_OPPORTUNITIES · PROPOSE_BUNDLE
  DENIED   MODIFY_CATALOG_PRICING · CREATE_PAYMENT · REFUND_PAYMENT
           MODIFY_USER_POLICY
```

Live at `GET /system/status`. Denial is explicit and wins over any allow entry;
an unregistered agent identity holds nothing at all.

## 8. Failure drills

`POST /drills/{policy-violation|payment-timeout|duplicate-webhook|tampered-webhook}`

Each exercises the same production code path the real failure would take. None
weakens a control: the policy drill is blocked by the real engine, and the
webhook drills go through real signature verification.
