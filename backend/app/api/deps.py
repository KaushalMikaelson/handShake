"""Request dependencies: authentication, then role checks.

The layering to keep in mind while reading this file:

    authentication  (here)      who is this human?
    role guard      (here)      which screens/endpoints may they reach?
    permission set  (policies/) which capabilities does an AGENT hold?
    policy engine   (policies/) is this specific transaction within limits?

Only the first two live here, and neither can influence the last two. There is
no role - not even ADMIN - that raises a spending limit or unblocks a purchase.
`test_admin_cannot_bypass_the_policy_engine` holds that line.
"""
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.enums import UserRole
from app.models import Buyer, Merchant, Session, User
from app.services import auth as auth_service


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not signed in.",
        headers={"WWW-Authenticate": "Cookie"},
    )


def current_session(
    request: Request, db: DbSession = Depends(get_db)
) -> tuple[User, Session]:
    """Resolve the session cookie to a live user, or 401."""
    token = request.cookies.get(auth_service.COOKIE_NAME)
    resolved = auth_service.resolve_session(db, token)
    if resolved is None:
        raise _unauthenticated()
    return resolved


def current_user(
    resolved: tuple[User, Session] = Depends(current_session),
) -> User:
    return resolved[0]


def optional_user(
    request: Request, db: DbSession = Depends(get_db)
) -> User | None:
    """For endpoints that are readable signed-out (e.g. the public catalog)."""
    token = request.cookies.get(auth_service.COOKIE_NAME)
    resolved = auth_service.resolve_session(db, token)
    return resolved[0] if resolved else None


def require_roles(*roles: UserRole) -> Callable[..., User]:
    """Endpoint guard: the signed-in user must hold one of these roles.

    ADMIN passes every guard - it is a *visibility* role for the demo operator,
    and grants no financial authority whatsoever.
    """
    allowed = {str(r) for r in roles} | {str(UserRole.ADMIN)}

    def _guard(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"This action requires one of: {', '.join(sorted(allowed))}.",
            )
        return user

    return _guard


def _admin_fallback_id(db: DbSession, user: User, model) -> str | None:
    """Admins observe the demo tenant when not linked to a profile of their own.

    This is a *read/observe* convenience for the operator. It confers no
    financial authority: whichever buyer is resolved, that buyer's own policy
    is what the engine enforces.
    """
    if user.role != str(UserRole.ADMIN):
        return None
    row = db.scalar(select(model))
    return row.id if row else None


def current_buyer(
    db: DbSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.BUYER)),
) -> Buyer:
    """The buyer principal the signed-in user acts for.

    Identity comes from the session, never from a client-supplied header - the
    previous X-Buyer-Id approach would have let any caller act as any buyer.
    """
    buyer_id = user.buyer_id or _admin_fallback_id(db, user, Buyer)
    if not buyer_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account is not linked to a buyer profile.",
        )
    buyer = db.get(Buyer, buyer_id)
    if buyer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyer profile not found.")
    return buyer


def current_merchant(
    db: DbSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT)),
) -> Merchant:
    merchant_id = user.merchant_id or _admin_fallback_id(db, user, Merchant)
    if not merchant_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account is not linked to a merchant profile.",
        )
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant profile not found.")
    return merchant
