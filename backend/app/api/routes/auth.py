"""Authentication endpoints.

The session token lives only in an httpOnly cookie. It is never returned in a
response body and never touches JavaScript, so an XSS bug on the frontend
cannot steal a login.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import current_session, current_user
from app.config import settings
from app.database import get_db
from app.enums import UserRole
from app.models import Session, User
from app.schemas.auth import (
    AuthStateOut,
    LoginRequest,
    MessageOut,
    RegisterRequest,
    SessionOut,
    UserOut,
)
from app.services import auth as auth_service
from app.services.security import PasswordPolicyError

router = APIRouter(prefix="/auth", tags=["auth"])

# Which nav destinations each role may reach. The server is the authority;
# the client renders what it is given rather than deciding for itself.
VIEWS_BY_ROLE = {
    UserRole.BUYER: ["buyer", "approvals", "audit"],
    UserRole.MERCHANT: ["merchant", "audit"],
    UserRole.ADMIN: ["buyer", "approvals", "merchant", "audit"],
}


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=UserRole(user.role),
        buyer_id=user.buyer_id,
        merchant_id=user.merchant_id,
        last_login_at=user.last_login_at,
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/login", response_model=AuthStateOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
) -> AuthStateOut:
    try:
        result = auth_service.login(
            db,
            email=payload.email,
            password=payload.password,
            user_agent=request.headers.get("user-agent", ""),
            ip_address=_client_ip(request),
        )
    except auth_service.AccountLocked as exc:
        # 429 rather than 401: the credentials are not the problem any more.
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    response.set_cookie(value=result.token, **auth_service.cookie_kwargs())
    return AuthStateOut(
        authenticated=True,
        user=_user_out(result.user),
        session_expires_at=result.session.expires_at,
        permitted_views=VIEWS_BY_ROLE.get(UserRole(result.user.role), []),
    )


@router.post("/register", response_model=AuthStateOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
) -> AuthStateOut:
    """Self-service signup, always as a BUYER.

    Role is never taken from the request body - that would let anyone register
    themselves an admin. New buyers get their own policy row seeded with
    conservative defaults.
    """
    from app.services.seed import create_buyer_profile

    try:
        buyer = create_buyer_profile(db, name=payload.name)
        user = auth_service.create_user(
            db,
            email=payload.email,
            name=payload.name,
            password=payload.password,
            role=UserRole.BUYER,
            buyer_id=buyer.id,
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()

    result = auth_service.login(
        db,
        email=payload.email,
        password=payload.password,
        user_agent=request.headers.get("user-agent", ""),
        ip_address=_client_ip(request),
    )
    response.set_cookie(value=result.token, **auth_service.cookie_kwargs())
    return AuthStateOut(
        authenticated=True,
        user=_user_out(user),
        session_expires_at=result.session.expires_at,
        permitted_views=VIEWS_BY_ROLE[UserRole.BUYER],
    )


@router.post("/logout", response_model=MessageOut)
def logout(
    response: Response,
    resolved: tuple[User, Session] = Depends(current_session),
    db: DbSession = Depends(get_db),
) -> MessageOut:
    """Revoke this session server-side, then clear the cookie.

    Order matters: the row is revoked first, so the token is dead even if the
    client never drops the cookie.
    """
    _, session = resolved
    auth_service.logout(db, session)
    response.delete_cookie(
        key=auth_service.COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="none" if settings.environment != "development" else "lax",
        secure=settings.environment != "development",
    )
    return MessageOut(detail="Signed out.")


@router.post("/logout-all", response_model=MessageOut)
def logout_all(
    response: Response,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
) -> MessageOut:
    """Sign out everywhere - the standard response to a suspected leak."""
    count = auth_service.logout_all(db, user)
    response.delete_cookie(
        key=auth_service.COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="none" if settings.environment != "development" else "lax",
        secure=settings.environment != "development",
    )
    return MessageOut(detail=f"Signed out of {count} session(s).")


@router.get("/me", response_model=AuthStateOut)
def me(request: Request, db: DbSession = Depends(get_db)) -> AuthStateOut:
    """Current auth state. Returns authenticated=false rather than 401, so the
    frontend can boot without treating "signed out" as an error."""
    token = request.cookies.get(auth_service.COOKIE_NAME)
    resolved = auth_service.resolve_session(db, token)
    if resolved is None:
        return AuthStateOut(authenticated=False)
    user, session = resolved
    return AuthStateOut(
        authenticated=True,
        user=_user_out(user),
        session_expires_at=session.expires_at,
        permitted_views=VIEWS_BY_ROLE.get(UserRole(user.role), []),
    )


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    resolved: tuple[User, Session] = Depends(current_session),
    db: DbSession = Depends(get_db),
) -> list[SessionOut]:
    """Every active login for this account, so a user can spot one they don't recognise."""
    user, current = resolved
    rows = db.scalars(
        select(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .order_by(Session.last_seen_at.desc())
    )
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            expires_at=s.expires_at,
            user_agent=s.user_agent,
            ip_address=s.ip_address,
            current=s.id == current.id,
        )
        for s in rows
        if s.is_active
    ]


@router.delete("/sessions/{session_id}", response_model=MessageOut)
def revoke_session(
    session_id: str,
    resolved: tuple[User, Session] = Depends(current_session),
    db: DbSession = Depends(get_db),
) -> MessageOut:
    """Revoke one other session by id. Ownership is checked, not assumed."""
    user, _ = resolved
    session = db.get(Session, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    auth_service.logout(db, session)
    return MessageOut(detail="Session revoked.")
