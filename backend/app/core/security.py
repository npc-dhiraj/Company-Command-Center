import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from app.core.config import settings

ph = PasswordHasher()

# Pre-computed dummy hash for timing attack mitigation when user/tenant is not found
DUMMY_PASSWORD_HASH = ph.hash("dummy_password_for_timing_mitigation_123!")


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    try:
        ph.verify(hashed_password, plain_password)
        new_hash = None
        if ph.check_needs_rehash(hashed_password):
            new_hash = ph.hash(plain_password)
        return True, new_hash
    except (VerificationError, VerifyMismatchError, InvalidHash):
        return False, None


def verify_dummy_password() -> None:
    try:
        ph.verify(DUMMY_PASSWORD_HASH, "dummy_password_for_timing_mitigation_123!")
    except Exception:
        pass


def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": str(role.value) if hasattr(role, "value") else str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }

    token: str = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
        return payload
    except (jwt.PyJWTError, ValueError) as exc:
        raise ValueError(f"Invalid access token: {exc}") from exc


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
