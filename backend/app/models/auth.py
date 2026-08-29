"""Authentication models: users and server-side sessions.

Deliberate boundary: this module answers "who is this human". It has no
knowledge of spending limits, capabilities or policy. Authentication decides
*whose* policy applies to a request - it never decides whether a purchase is
allowed, and no role defined here can raise a limit. See docs/safety.md,
"Authentication is not authorization".

Sessions are server-side and opaque rather than JWTs, because the requirement
is a real logout: revoking a row is instant and total, whereas a stateless
token stays valid until it expires no matter what the user clicks.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.enums import UserRole


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # bcrypt hash. The plaintext password is never stored, logged or returned -
    # `test_password_is_never_stored_in_plaintext` asserts this.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(32), default=UserRole.BUYER, nullable=False)

    # Which domain principal this login acts for. A buyer user carries the
    # buyer_id whose policy governs their agent; a merchant user carries the
    # merchant_id whose catalog they administer.
    buyer_id: Mapped[str | None] = mapped_column(
        ForeignKey("buyers.id"), nullable=True, index=True
    )
    merchant_id: Mapped[str | None] = mapped_column(
        ForeignKey("merchants.id"), nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Session(Base):
    """An active login.

    The raw session token is returned to the browser once, in an httpOnly
    cookie, and only its SHA-256 hash is stored here. A database leak therefore
    does not hand an attacker usable session tokens - the same reasoning that
    applies to passwords applies to long-lived bearer credentials.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set on logout. Presence of a value is what makes the session dead, and it
    # is checked on every request - logout is immediate, not eventual.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user_agent: Mapped[str] = mapped_column(String(300), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")

    @property
    def is_active(self) -> bool:
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:          # SQLite round-trips naive datetimes
            expires = expires.replace(tzinfo=timezone.utc)
        return self.revoked_at is None and expires > now
