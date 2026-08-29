"""End-to-end API tests through the real FastAPI app.

These use a TestClient against a temp database with the app's own dependency
overrides, so routing, validation and serialisation are all exercised.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db


@pytest.fixture(autouse=True)
def _no_startup_seed(monkeypatch):
    """The `db` fixture already seeds; stop startup from touching the real DB."""
    monkeypatch.setattr("app.main.init_db", lambda: None)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ------------------------------------------------------------------ catalog
def test_catalog_is_machine_readable_with_documented_fields(client):
    r = client.get("/catalog")
    assert r.status_code == 200
    body = r.json()
    assert body["amount_unit"] == "paise"
    assert body["count"] == 5
    required = {
        "product_id", "name", "price", "currency", "category",
        "stock_available", "attributes", "bundle_eligible", "max_discount_pct",
    }
    for product in body["products"]:
        assert required <= set(product)
        assert isinstance(product["price"], int)  # never a float


def test_catalog_filters_are_applied(client):
    r = client.get("/catalog", params={"category": "accessories", "max_price": 50_000})
    products = r.json()["products"]
    assert [p["product_id"] for p in products] == ["prod_cable_aux"]


def test_openapi_schema_is_published_for_agents(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/catalog" in r.json()["paths"]


# --------------------------------------------------------------- shop flows
def test_shop_auto_purchase_completes(client):
    r = client.post(
        "/buyer/shop",
        json={"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"},
    )
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "completed"
    assert body["policy"]["decision"] == "AUTO_APPROVE"
    assert body["transaction"]["status"] == "CAPTURED"


def test_shop_above_threshold_routes_to_approval(client):
    r = client.post(
        "/buyer/shop",
        json={"query": "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony"},
    )
    body = r.json()
    assert body["status"] == "awaiting_approval"
    assert body["razorpay_called"] is False
    assert body["approval"]["status"] == "PENDING"
    assert body["transaction"] is None


def test_shop_without_a_budget_asks_for_one(client):
    r = client.post("/buyer/shop", json={"query": "Buy me some good headphones"})
    body = r.json()
    assert body["status"] == "needs_clarification"
    assert body["needs_clarification"] is True
    assert body["clarification_question"]


def test_shop_over_limit_is_blocked_with_the_rule_named(client):
    r = client.post(
        "/buyer/shop",
        json={"query": "Buy premium Sennheiser wireless headphones, budget up to Rs 20,000"},
    )
    body = r.json()
    assert body["status"] == "blocked"
    assert body["policy"]["failed_rule"] == "budget.max_transaction"
    assert body["razorpay_called"] is False


def test_empty_query_is_rejected_by_validation(client):
    assert client.post("/buyer/shop", json={"query": ""}).status_code == 422


# ---------------------------------------------------------------- approvals
def test_approve_executes_payment(client):
    shop = client.post(
        "/buyer/shop",
        json={"query": "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony"},
    ).json()
    approval_id = shop["approval"]["approval_id"]

    r = client.post(f"/approvals/{approval_id}/decision",
                    json={"decision": "approve", "actor": "aditi"})
    body = r.json()
    assert body["status"] == "completed"
    assert body["transaction"]["status"] == "CAPTURED"


def test_reject_terminates_without_payment(client):
    shop = client.post(
        "/buyer/shop",
        json={"query": "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony"},
    ).json()
    approval_id = shop["approval"]["approval_id"]

    body = client.post(f"/approvals/{approval_id}/decision",
                       json={"decision": "reject", "actor": "aditi"}).json()
    assert body["status"] == "rejected"
    assert body["transaction"] is None
    assert body["razorpay_called"] is False
    # and the buyer's budget is untouched
    assert client.get("/buyer/state").json()["spent_today"] == 0


def test_a_decided_approval_cannot_be_decided_again(client):
    """Guards against a double-submit turning into a second charge."""
    shop = client.post(
        "/buyer/shop",
        json={"query": "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony"},
    ).json()
    approval_id = shop["approval"]["approval_id"]

    assert client.post(f"/approvals/{approval_id}/decision",
                       json={"decision": "approve"}).status_code == 200
    second = client.post(f"/approvals/{approval_id}/decision", json={"decision": "approve"})
    assert second.status_code == 409


def test_invalid_decision_value_is_rejected(client):
    assert client.post("/approvals/nonexistent/decision",
                       json={"decision": "maybe"}).status_code == 422


# ------------------------------------------------------------ autonomy levels
def test_level_1_produces_a_recommendation_but_no_purchase(client):
    client.put("/buyer/policy", json={"autonomy_level": "L1_RECOMMEND"})
    body = client.post(
        "/buyer/shop",
        json={"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"},
    ).json()
    assert body["status"] == "recommendation_only"
    assert body["transaction"] is None
    assert body["recommendation"]["selected_product_id"] == "prod_cable_aux"


def test_level_2_asks_even_below_the_auto_threshold(client):
    client.put("/buyer/policy", json={"autonomy_level": "L2_PREPARE"})
    body = client.post(
        "/buyer/shop",
        json={"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"},
    ).json()
    assert body["status"] == "awaiting_approval"


def test_tightening_the_policy_takes_effect_immediately(client):
    client.put("/buyer/policy", json={"max_transaction": 10_000})  # Rs 100
    body = client.post(
        "/buyer/shop",
        json={"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"},
    ).json()
    assert body["status"] == "blocked"
    assert body["policy"]["failed_rule"] == "budget.max_transaction"


# ----------------------------------------------------------------- audit API
def test_audit_timeline_covers_the_required_event_set(client):
    """US-9's minimum event set must appear for a successful transaction."""
    shop = client.post(
        "/buyer/shop",
        json={"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"},
    ).json()
    intent_id = shop["intent"]["intent_id"]

    timeline = client.get(f"/audit/timeline/{intent_id}").json()
    actions = [e["action"] for e in timeline["events"]]

    for required in [
        "USER_INTENT_RECEIVED", "CATALOG_SEARCH", "PRODUCT_SELECTED",
        "PERMISSION_CHECK", "POLICY_CHECK", "RAZORPAY_ORDER_CREATED",
        "PAYMENT_CONFIRMED", "WEBHOOK_PROCESSED", "ORDER_COMPLETED",
    ]:
        assert required in actions, f"{required} missing from {actions}"

    # a bundle decision is always recorded, one way or the other
    assert {"OFFER_GENERATED", "NO_BUNDLE_OFFERED"} & set(actions)
    # and the timeline is strictly ordered
    assert [e["sequence"] for e in timeline["events"]] == sorted(
        e["sequence"] for e in timeline["events"]
    )


def test_every_audit_event_carries_a_timestamp_and_reason(client):
    client.post("/buyer/shop",
                json={"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"})
    for event in client.get("/audit/events").json():
        assert event["timestamp"]
        assert event["reason"].strip(), f"{event['action']} has no reason"
        assert event["agent_id"]


def test_audit_api_exposes_no_write_route(client):
    """Immutability, checked at the routing layer."""
    paths = client.get("/openapi.json").json()["paths"]
    for path, methods in paths.items():
        if path.startswith("/audit"):
            assert set(methods) <= {"get"}, f"{path} exposes {set(methods)}"


# ------------------------------------------------------------- merchant API
def test_rejecting_an_opportunity_stops_the_agent_offering_it(client):
    """US-5b: only merchant-approved pairings may reach a buyer."""
    for opportunity in client.get("/merchant/opportunities").json():
        client.post(f"/merchant/opportunities/{opportunity['id']}/reject")

    body = client.post(
        "/buyer/shop",
        json={"query": "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony"},
    ).json()
    assert body["bundle"]["offered"] is False


def test_merchant_metrics_report_completed_orders(client):
    client.post("/buyer/shop",
                json={"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"})
    metrics = client.get("/merchant/metrics").json()
    assert metrics["orders_completed"] == 1
    assert metrics["revenue"] == 29_900


# --------------------------------------------------------------- drill routes
def test_policy_violation_drill_reports_no_gateway_call(client):
    body = client.post("/drills/policy-violation").json()
    assert body["status"] == "blocked"
    assert body["razorpay_called"] is False


def test_duplicate_webhook_drill_reports_the_second_as_ignored(client):
    client.post("/buyer/shop",
                json={"query": "Buy me a braided aux cable for my headphones, budget Rs 1000"})
    body = client.post("/drills/duplicate-webhook").json()
    assert body["first_delivery"]["duplicate"] is False
    assert body["second_delivery"]["duplicate"] is True


def test_forged_webhook_is_rejected_over_http(client):
    r = client.post(
        "/webhooks/razorpay",
        content=b'{"event":"payment.captured"}',
        headers={"x-razorpay-signature": "bogus", "x-razorpay-event-id": "e1"},
    )
    assert r.status_code == 400
    assert r.json()["status"] == "invalid_signature"


# ------------------------------------------------------------------- system
def test_system_status_declares_which_mode_it_is_running_in(client):
    body = client.get("/system/status").json()
    assert body["payments"]["mode"] in {"simulator", "razorpay_test"}
    assert len(body["security_principles"]) == 7
    assert "REFUND_PAYMENT" in body["permissions"]["buyer_agent"]["denied"]
