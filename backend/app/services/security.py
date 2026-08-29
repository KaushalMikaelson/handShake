"""Password hashing and session-token primitives.

Three choices worth stating, because each is a place auth systems commonly go
wrong:

1. **bcrypt, not a plain hash.** Passwords are hashed with a per-password salt
   and a deliberate work factor. SHA-256 of a password is a rounding error to
   brute-force; bcrypt is not.

2. **Tokens are stored hashed.** A session token is a bearer credential - anyone
   holding it is the user. We keep only its SHA-256, so a database leak yields
   nothing usable. (SHA-256 without a work factor is correct *here*: the token
   is 256 bits of CSPRNG output, so there is no dictionary to attack.)

3. **Constant-time comparison** everywhere a secret is checked, so response
   timing does not leak how much of a value was correct.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt

from app.config import settings

# Cost factor. 12 is the common production floor; each +1 doubles the work.
# Configurable only so the test suite can run fast - see Settings.bcrypt_rounds.
BCRYPT_ROUNDS = settings.bcrypt_rounds

# bcrypt silently truncates at 72 bytes, so anything longer is rejected up
# front rather than being quietly accepted with its tail ignored.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8

TOKEN_BYTES = 32  # 256 bits of entropy


class PasswordPolicyError(ValueError):
    """Raised when a proposed password fails the minimum requirements."""


def validate_password(password: str) -> None:
    """Enforce the minimum password rules. Raises PasswordPolicyError."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise PasswordPolicyError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes."
        )
    if password.islower() or password.isupper():
        raise PasswordPolicyError("Password must mix upper and lower case letters.")
    if not any(c.isdigit() for c in password):
        raise PasswordPolicyError("Password must contain at least one digit.")


def hash_password(password: str) -> str:
    validate_password(password)
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(settings.bcrypt_rounds)
    ).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time password check. Never raises on malformed input."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode())
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """A fresh, unguessable session token. Returned to the client exactly once."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """The stored form of a session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)
