"""Authentication and authorization tests.

The single most important test here is
`test_admin_role_cannot_bypass_the_policy_engine`. Adding login to a system
whose whole claim is "bounded autonomy" creates exactly one new way to ruin
that claim: letting an identity become an exemption. It must not.
"""
import pytest
from sqlalchemy import select

from app.enums import AuditAction
from app.models import ApprovalRequest, AuditEvent, Session, User
from app.services import auth as auth_service
from app.services.security import (
    PasswordPolicyError,
    hash_password,
    hash_token,
    generate_session_token,
    validate_password,
    verify_password,
)

DEMO_PASSWORD = "Demo@1234"
BUYER_EMAIL = "aditi@handshake.demo"
MERCHANT_EMAIL = "merchant@audiohub.demo"
ADMIN_EMAIL = "admin@handshake.demo"


# ====================================================================
# password handling
# ====================================================================
def test_password_is_never_stored_in_plaintext(db):
    """The most basic promise: the database must not contain the password."""
    for user in db.scalars(select(User)):
        assert DEMO_PASSWORD not in user.password_hash
        assert user.password_hash.startswith("$2b$")
        assert len(user.password_hash) == 60


def test_identical_passwords_produce_different_hashes(db):
    """Per-password salting: identical passwords must not collide in the DB."""
    hashes = {u.password_hash for u in db.scalars(select(User))}
    assert len(hashes) == db.query(User).count()


def test_password_verification_round_trips():
    h = hash_password("Correct1Horse")
    assert verify_password("Correct1Horse", h) is True
    assert verify_password("correct1horse", h) is False
    assert verify_password("", h) is False


def test_verification_of_a_malformed_hash_fails_closed():
    """A corrupt hash must deny access, never raise and never pass."""
    assert verify_password("anything", "not-a-bcrypt-hash") is False
    assert verify_password("anything", "") is False


@pytest.mark.parametrize(
    "weak",
    ["short1A", "alllowercase1", "ALLUPPERCASE1", "NoDigitsAtAll", "1234567"],
)
def test_weak_passwords_are_rejected(weak):
    with pytest.raises(PasswordPolicyError):
        validate_password(weak)


def test_overlong_password_is_rejected_rather_than_silently_truncated():
    """bcrypt ignores bytes past 72; accepting them would be a silent downgrade."""
    with pytest.raises(PasswordPolicyError):
        validate_password("A1" + "x" * 100)


# ====================================================================
# login
# ====================================================================
def test_login_succeeds_and_sets_an_httponly_cookie(anon_client):
    r = anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": DEMO_PASSWORD}
    )
    assert r.status_code == 200
    assert r.json()["authenticated"] is True
    assert r.json()["user"]["role"] == "buyer"

    cookie = r.headers["set-cookie"]
    assert "httponly" in cookie.lower()
    assert "samesite=strict" in cookie.lower().replace(" ", "")


def test_login_response_never_leaks_the_token_or_hash(anon_client):
    r = anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": DEMO_PASSWORD}
    )
    body = r.text
    assert "password_hash" not in body
    assert "token" not in body.lower()


def test_wrong_password_is_rejected(anon_client):
    r = anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": "WrongPass1"}
    )
    assert r.status_code == 401


def test_unknown_and_known_emails_give_the_same_error(anon_client):
    """No user enumeration: a stranger cannot learn which emails have accounts."""
    unknown = anon_client.post(
        "/auth/login", json={"email": "nobody@nowhere.demo", "password": "WrongPass1"}
    )
    known = anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": "WrongPass1"}
    )
    assert unknown.status_code == known.status_code == 401
    assert unknown.json()["detail"] == known.json()["detail"]


def test_repeated_failures_lock_the_account(anon_client, db):
    """Brute-force throttling, and the lock is recorded in the audit trail."""
    for _ in range(auth_service.MAX_FAILED_LOGINS):
        anon_client.post(
            "/auth/login", json={"email": BUYER_EMAIL, "password": "WrongPass1"}
        )

    locked = anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": "WrongPass1"}
    )
    assert locked.status_code == 429

    # even the CORRECT password is refused while locked
    correct = anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": DEMO_PASSWORD}
    )
    assert correct.status_code == 429

    actions = [e.action for e in db.scalars(select(AuditEvent))]
    assert AuditAction.ACCOUNT_LOCKED in actions


def test_successful_login_clears_the_failure_counter(anon_client, db):
    for _ in range(auth_service.MAX_FAILED_LOGINS - 1):
        anon_client.post(
            "/auth/login", json={"email": BUYER_EMAIL, "password": "WrongPass1"}
        )
    assert anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": DEMO_PASSWORD}
    ).status_code == 200

    user = db.scalar(select(User).where(User.email == BUYER_EMAIL))
    assert user.failed_login_count == 0
    assert user.locked_until is None


def test_logins_are_audited(anon_client, db):
    anon_client.post("/auth/login", json={"email": BUYER_EMAIL, "password": "WrongPass1"})
    anon_client.post("/auth/login", json={"email": BUYER_EMAIL, "password": DEMO_PASSWORD})
    actions = [e.action for e in db.scalars(select(AuditEvent))]
    assert AuditAction.LOGIN_FAILED in actions
    assert AuditAction.LOGIN_SUCCEEDED in actions


# ====================================================================
# sessions and logout
# ====================================================================
def test_signed_out_requests_are_rejected(anon_client):
    for endpoint in ["/buyer/state", "/approvals", "/merchant/metrics", "/auth/sessions"]:
        assert anon_client.get(endpoint).status_code == 401, endpoint


def test_public_catalog_stays_readable_signed_out(anon_client):
    """The catalog is the agent-readable contract; auth must not wall it off."""
    assert anon_client.get("/catalog").status_code == 200


def test_me_reports_signed_out_without_erroring(anon_client):
    r = anon_client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["authenticated"] is False


def test_logout_revokes_the_session_server_side(client, db):
    """The token must die on the server, not merely be dropped by the browser."""
    assert client.get("/buyer/state").status_code == 200

    assert client.post("/auth/logout").status_code == 200

    session = db.scalar(select(Session))
    assert session.revoked_at is not None

    # the client still holds the cookie value; it must no longer work
    assert client.get("/buyer/state").status_code == 401


def test_a_revoked_token_cannot_be_replayed(client, db):
    """Explicitly re-present the raw cookie after logout."""
    raw = client.cookies.get(auth_service.COOKIE_NAME)
    client.post("/auth/logout")

    client.cookies.set(auth_service.COOKIE_NAME, raw)
    assert client.get("/buyer/state").status_code == 401


def test_expired_sessions_are_rejected(client, db):
    from datetime import datetime, timedelta, timezone

    session = db.scalar(select(Session))
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert client.get("/buyer/state").status_code == 401


def test_a_forged_token_is_rejected(anon_client):
    anon_client.cookies.set(auth_service.COOKIE_NAME, generate_session_token())
    assert anon_client.get("/buyer/state").status_code == 401


def test_only_the_token_hash_is_stored(client, db):
    """A database leak must not yield usable session tokens."""
    raw = client.cookies.get(auth_service.COOKIE_NAME)
    session = db.scalar(select(Session))
    assert session.token_hash != raw
    assert session.token_hash == hash_token(raw)
    assert len(session.token_hash) == 64


def test_logout_all_revokes_every_session(db, anon_client):
    from fastapi.testclient import TestClient

    from app.main import app

    # two independent logins for the same account
    first = anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": DEMO_PASSWORD}
    )
    assert first.status_code == 200
    second_client = TestClient(app)
    second_client.post("/auth/login", json={"email": BUYER_EMAIL, "password": DEMO_PASSWORD})

    assert db.query(Session).filter(Session.revoked_at.is_(None)).count() == 2

    anon_client.post("/auth/logout-all")
    assert db.query(Session).filter(Session.revoked_at.is_(None)).count() == 0
    assert second_client.get("/buyer/state").status_code == 401


def test_sessions_endpoint_lists_only_your_own(client, db):
    sessions = client.get("/auth/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["current"] is True


def test_cannot_revoke_another_users_session(client, db, anon_client):
    """Session ids are not capabilities - ownership is verified."""
    anon_client.post("/auth/login", json={"email": MERCHANT_EMAIL, "password": DEMO_PASSWORD})
    merchant_user = db.scalar(select(User).where(User.email == MERCHANT_EMAIL))
    other = db.scalar(select(Session).where(Session.user_id == merchant_user.id))

    assert client.delete(f"/auth/sessions/{other.id}").status_code == 404
    db.refresh(other)
    assert other.revoked_at is None


# ====================================================================
# roles and ownership
# ====================================================================
def test_buyer_cannot_reach_merchant_endpoints(client):
    assert client.get("/merchant/metrics").status_code == 403
    assert client.get("/merchant/opportunities").status_code == 403


def test_merchant_cannot_reach_buyer_endpoints(merchant_client):
    assert merchant_client.get("/buyer/state").status_code == 403
    assert merchant_client.post(
        "/buyer/shop", json={"query": "Buy me headphones under Rs 5000"}
    ).status_code == 403


def test_admin_can_reach_both_dashboards(admin_client):
    assert admin_client.get("/buyer/state").status_code == 200
    assert admin_client.get("/merchant/metrics").status_code == 200


def test_permitted_views_are_decided_by_the_server(anon_client):
    buyer = anon_client.post(
        "/auth/login", json={"email": BUYER_EMAIL, "password": DEMO_PASSWORD}
    ).json()
    assert buyer["permitted_views"] == ["buyer", "approvals", "audit"]
    anon_client.post("/auth/logout")

    merchant = anon_client.post(
        "/auth/login", json={"email": MERCHANT_EMAIL, "password": DEMO_PASSWORD}
    ).json()
    assert "buyer" not in merchant["permitted_views"]


def test_a_buyer_cannot_see_or_decide_another_buyers_approval(client, db, anon_client):
    """Ownership, not merely authentication, gates an approval decision."""
    shop = client.post(
        "/buyer/shop",
        json={"query": "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony"},
    ).json()
    approval_id = shop["approval"]["approval_id"]

    # a second buyer registers and tries to approve someone else's purchase
    anon_client.post(
        "/auth/register",
        json={"email": "mallory@handshake.demo", "name": "Mallory", "password": "Demo@1234"},
    )
    assert anon_client.get(f"/approvals/{approval_id}").status_code == 404
    assert anon_client.post(
        f"/approvals/{approval_id}/decision", json={"decision": "approve"}
    ).status_code == 404

    approval = db.get(ApprovalRequest, approval_id)
    assert approval.status == "PENDING"


def test_approval_records_the_authenticated_actor_not_a_claimed_one(client, db):
    """US-12: approval actions are attributable to a real, verified actor."""
    shop = client.post(
        "/buyer/shop",
        json={"query": "Buy me wireless noise cancelling headphones under Rs 10,000, prefer Sony"},
    ).json()
    approval_id = shop["approval"]["approval_id"]

    # the body cannot name a different actor - the field does not exist
    result = client.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": "approve", "actor": "somebody-else"},
    ).json()

    assert result["approval"]["decided_by"] == "Aditi Rao <aditi@handshake.demo>"
    granted = db.scalar(
        select(AuditEvent).where(AuditEvent.action == AuditAction.APPROVAL_GRANTED)
    )
    assert "aditi@handshake.demo" in granted.reason


# ====================================================================
# registration
# ====================================================================
def test_registration_creates_a_buyer_with_conservative_defaults(anon_client):
    r = anon_client.post(
        "/auth/register",
        json={"email": "new@handshake.demo", "name": "New Buyer", "password": "Demo@1234"},
    )
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "buyer"

    policy = anon_client.get("/buyer/state").json()["policy"]
    # a brand-new account must ask before spending, not auto-buy
    assert policy["autonomy_level"] == "L2_PREPARE"
    assert policy["max_transaction"] <= 300_000


def test_registration_cannot_self_assign_a_privileged_role(anon_client):
    """Role is never read from the request body."""
    r = anon_client.post(
        "/auth/register",
        json={
            "email": "sneaky@handshake.demo",
            "name": "Sneaky",
            "password": "Demo@1234",
            "role": "admin",
        },
    )
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "buyer"
    assert anon_client.get("/merchant/metrics").status_code == 403


def test_duplicate_email_is_rejected(anon_client):
    assert anon_client.post(
        "/auth/register",
        json={"email": BUYER_EMAIL, "name": "Impostor", "password": "Demo@1234"},
    ).status_code == 409


def test_weak_password_is_rejected_at_registration(anon_client):
    r = anon_client.post(
        "/auth/register",
        json={"email": "weak@handshake.demo", "name": "Weak", "password": "password"},
    )
    assert r.status_code == 422


# ====================================================================
# the line that must not move
# ====================================================================
def test_admin_role_cannot_bypass_the_policy_engine(admin_client):
    """Authentication is not authorization.

    Adding logins introduces exactly one tempting mistake: treating a
    privileged identity as a spending exemption. An admin attempting an
    over-limit purchase must be blocked by the same rule as anyone else, and
    Razorpay must still never be called.
    """
    body = admin_client.post("/drills/policy-violation").json()
    assert body["status"] == "blocked"
    assert body["policy"]["failed_rule"] == "budget.max_transaction"
    assert body["razorpay_called"] is False


def test_no_role_appears_in_the_policy_engines_inputs():
    """Structural proof: the engine's signature has nowhere to put an identity."""
    import inspect

    from app.policies import evaluate

    params = set(inspect.signature(evaluate).parameters)
    assert params == {"purchase", "policy", "merchant_policy", "context"}
    for forbidden in ("user", "role", "session", "actor", "is_admin"):
        assert forbidden not in params


def test_authenticating_does_not_change_any_spending_limit(client, admin_client):
    """The same buyer policy applies regardless of which identity reads it."""
    as_buyer = client.get("/buyer/state").json()["policy"]
    as_admin = admin_client.get("/buyer/state").json()["policy"]
    assert as_buyer == as_admin
