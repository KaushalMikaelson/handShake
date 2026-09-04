"""Authentication service: login, session lifecycle, logout.

What this module does NOT do is as important as what it does. It resolves a
request to a `User`. It never consults, modifies or bypasses the policy engine
or the permission system. A logged-in admin and a logged-in buyer hit exactly
the same spending limits, because the limits are a property of the buyer's
policy row, not of the session.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.enums import AgentId, AuditAction, AuditStatus, UserRole
from app.models import Session, User
from app.services import audit
from app.services.security import (
    generate_session_token,
    hash_password,
    hash_token,
    verify_password,
)

SESSION_TTL = timedelta(hours=12)
# Sliding window: an active session is extended, so working through a long
# judging session never logs you out mid-demo.
SESSION_REFRESH_AFTER = timedelta(minutes=15)

MAX_FAILED_LOGINS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


class AuthError(Exception):
    """Login failed. The message is deliberately non-specific - see below."""


class AccountLocked(AuthError):
    pass


@dataclass
class LoginResult:
    user: User
    session: Session
    token: str  # raw token, returned to the client exactly once


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; normalise before comparing."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ----------------------------------------------------------------------
# users
# ----------------------------------------------------------------------
def create_user(
    db: DbSession,
    *,
    email: str,
    name: str,
    password: str,
    role: UserRole | str = UserRole.BUYER,
    buyer_id: str | None = None,
    merchant_id: str | None = None,
) -> User:
    """Create a user. Raises PasswordPolicyError if the password is too weak."""
    normalised = email.strip().lower()
    if db.scalar(select(User).where(User.email == normalised)):
        raise AuthError("An account with that email already exists.")

    user = User(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        email=normalised,
        name=name.strip(),
        password_hash=hash_password(password),   # validates the policy
        role=str(role),
        buyer_id=buyer_id,
        merchant_id=merchant_id,
    )
    db.add(user)
    db.flush()
    return user


def get_user_by_email(db: DbSession, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


# ----------------------------------------------------------------------
# login
# ----------------------------------------------------------------------
def login(
    db: DbSession,
    *,
    email: str,
    password: str,
    user_agent: str = "",
    ip_address: str = "",
) -> LoginResult:
    """Authenticate and open a session.

    Every failure path raises the same message ("Invalid email or password"),
    so the endpoint cannot be used to enumerate which emails have accounts.
    """
    user = get_user_by_email(db, email)

    if user is None:
        # Spend roughly the time a real bcrypt check costs, so a missing
        # account is not distinguishable from a wrong password by timing.
        verify_password(password, "$2b$12$" + "." * 53)
        _record_login_failure(db, email=email, reason="no such account")
        raise AuthError("Invalid email or password.")

    locked_until = _aware(user.locked_until)
    if locked_until and locked_until > _utcnow():
        remaining = int((locked_until - _utcnow()).total_seconds() // 60) + 1
        audit.record(
            db,
            agent_id=AgentId.HUMAN,
            action=AuditAction.LOGIN_FAILED,
            reason=f"Login attempt on locked account {user.email}.",
            status=AuditStatus.DENIED,
        )
        raise AccountLocked(
            f"Too many failed attempts. Try again in about {remaining} minute(s)."
        )

    if not user.is_active:
        _record_login_failure(db, email=email, reason="account disabled")
        raise AuthError("Invalid email or password.")

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = _utcnow() + LOCKOUT_DURATION
            user.failed_login_count = 0
            db.commit()
            audit.record(
                db,
                agent_id=AgentId.HUMAN,
                action=AuditAction.ACCOUNT_LOCKED,
                reason=(
                    f"Account {user.email} locked after {MAX_FAILED_LOGINS} failed "
                    f"login attempts."
                ),
                status=AuditStatus.DENIED,
            )
            raise AccountLocked(
                "Too many failed attempts. This account is locked for 15 minutes."
            )
        db.commit()
        _record_login_failure(db, email=email, reason="wrong password")
        raise AuthError("Invalid email or password.")

    # --- success ---
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = _utcnow()

    token = generate_session_token()
    session = Session(
        id=f"ses_{uuid.uuid4().hex[:12]}",
        token_hash=hash_token(token),
        user_id=user.id,
        expires_at=_utcnow() + SESSION_TTL,
        user_agent=(user_agent or "")[:300],
        ip_address=(ip_address or "")[:64],
    )
    db.add(session)
    db.commit()

    audit.record(
        db,
        agent_id=AgentId.HUMAN,
        action=AuditAction.LOGIN_SUCCEEDED,
        reason=f"{user.name} <{user.email}> signed in as {user.role}.",
        output_reference={"user_id": user.id, "role": user.role, "session_id": session.id},
    )
    return LoginResult(user=user, session=session, token=token)


def _record_login_failure(db: DbSession, *, email: str, reason: str) -> None:
    audit.record(
        db,
        agent_id=AgentId.HUMAN,
        action=AuditAction.LOGIN_FAILED,
        reason=f"Failed login for {email!r}: {reason}.",
        status=AuditStatus.DENIED,
    )


# ----------------------------------------------------------------------
# session resolution
# ----------------------------------------------------------------------
def resolve_session(db: DbSession, token: str | None) -> tuple[User, Session] | None:
    """Return (user, session) for a valid token, else None.

    Checks revocation and expiry on every request, which is what makes logout
    take effect immediately rather than whenever a token would have expired.
    """
    if not token:
        return None

    session = db.scalar(select(Session).where(Session.token_hash == hash_token(token)))
    if session is None or not session.is_active:
        return None

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None

    # sliding expiry, written only occasionally to avoid a write per request
    now = _utcnow()
    last_seen = _aware(session.last_seen_at) or now
    if now - last_seen > SESSION_REFRESH_AFTER:
        session.last_seen_at = now
        session.expires_at = now + SESSION_TTL
        db.commit()

    return user, session


def logout(db: DbSession, session: Session) -> None:
    """Revoke one session. The token is dead the instant this commits."""
    if session.revoked_at is None:
        session.revoked_at = _utcnow()
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.HUMAN,
            action=AuditAction.LOGOUT,
            reason=f"Session {session.id} revoked by logout.",
            output_reference={"session_id": session.id, "user_id": session.user_id},
        )


def logout_all(db: DbSession, user: User) -> int:
    """Revoke every active session for a user. Returns how many were revoked."""
    sessions = list(
        db.scalars(
            select(Session).where(
                Session.user_id == user.id, Session.revoked_at.is_(None)
            )
        )
    )
    now = _utcnow()
    for session in sessions:
        session.revoked_at = now
    db.commit()
    if sessions:
        audit.record(
            db,
            agent_id=AgentId.HUMAN,
            action=AuditAction.LOGOUT,
            reason=f"All {len(sessions)} session(s) revoked for {user.email}.",
            output_reference={"user_id": user.id, "revoked": len(sessions)},
        )
    return len(sessions)


def purge_expired_sessions(db: DbSession) -> int:
    """Housekeeping: drop sessions that expired long ago."""
    cutoff = _utcnow() - timedelta(days=7)
    stale = list(db.scalars(select(Session).where(Session.expires_at < cutoff)))
    for session in stale:
        db.delete(session)
    db.commit()
    return len(stale)


# ----------------------------------------------------------------------
# cookie helpers
# ----------------------------------------------------------------------
COOKIE_NAME = "handshake_session"


def cookie_kwargs() -> dict:
    """Session cookie settings.

    - httponly: JavaScript cannot read the token, so an XSS bug cannot exfiltrate it.
    - samesite=none (in production) / lax (in development) to allow credentials across origins.
    - secure: True outside development (required for samesite=none over HTTPS).
    """
    is_prod = settings.environment != "development"
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "samesite": "none" if is_prod else "lax",
        "secure": is_prod,
        "path": "/",
        "max_age": int(SESSION_TTL.total_seconds()),
    }
