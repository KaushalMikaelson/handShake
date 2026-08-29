"""Authentication request/response contracts.

Note that no response model here carries `password_hash` - the field simply
does not exist on any outbound schema, so it cannot leak through a serialiser
by accident.
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    buyer_id: str | None = None
    merchant_id: str | None = None
    last_login_at: datetime | None = None


class SessionOut(BaseModel):
    id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str
    ip_address: str
    current: bool = False


class AuthStateOut(BaseModel):
    """What the frontend needs to render the shell for a signed-in user."""

    authenticated: bool
    user: UserOut | None = None
    session_expires_at: datetime | None = None
    # which nav destinations this role may reach - the server decides, the
    # client only renders what it is told
    permitted_views: list[str] = Field(default_factory=list)


class MessageOut(BaseModel):
    detail: str
