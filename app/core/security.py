from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import get_settings

_password_hasher = PasswordHasher()


@dataclass(frozen=True)
class RefreshTokenData:
    token: str
    jti: str
    family_id: str
    expires_at: datetime
    expires_in_seconds: int


def _access_signing_key() -> str:
    settings = get_settings()
    return settings.jwt_access_secret_key or settings.jwt_secret_key


def _refresh_signing_key() -> str:
    settings = get_settings()
    return settings.jwt_refresh_secret_key or settings.jwt_secret_key


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    return True


def create_access_token(*, subject: str, expires_delta: timedelta | None = None) -> tuple[str, int]:
    settings = get_settings()
    lifetime = expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    expire_at = datetime.now(UTC) + lifetime
    payload = {
        "sub": subject,
        "type": "access",
        "exp": expire_at,
    }
    token = jwt.encode(payload, _access_signing_key(), algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def create_refresh_token(
    *,
    subject: str,
    family_id: str | None = None,
    jti: str | None = None,
    expires_delta: timedelta | None = None,
) -> RefreshTokenData:
    settings = get_settings()
    lifetime = expires_delta or timedelta(minutes=settings.jwt_refresh_token_expire_minutes)
    expire_at = datetime.now(UTC) + lifetime
    token_jti = jti or str(uuid4())
    token_family_id = family_id or str(uuid4())
    payload = {
        "sub": subject,
        "type": "refresh",
        "jti": token_jti,
        "family_id": token_family_id,
        "exp": expire_at,
    }
    token = jwt.encode(payload, _refresh_signing_key(), algorithm=settings.jwt_algorithm)
    return RefreshTokenData(
        token=token,
        jti=token_jti,
        family_id=token_family_id,
        expires_at=expire_at,
        expires_in_seconds=int(lifetime.total_seconds()),
    )


def decode_access_token(token: str) -> dict[str, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, _access_signing_key(), algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid access token.") from exc

    token_type = payload.get("type")
    subject = payload.get("sub")

    if token_type != "access" or not isinstance(subject, str):
        raise ValueError("Invalid access token payload.")

    return {"sub": subject}


def decode_refresh_token(token: str) -> dict[str, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, _refresh_signing_key(), algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid refresh token.") from exc

    token_type = payload.get("type")
    subject = payload.get("sub")
    jti = payload.get("jti")
    family_id = payload.get("family_id")

    if (
        token_type != "refresh"
        or not isinstance(subject, str)
        or not isinstance(jti, str)
        or not isinstance(family_id, str)
    ):
        raise ValueError("Invalid refresh token payload.")

    return {"sub": subject, "jti": jti, "family_id": family_id}


def hash_refresh_token_identifier(jti: str) -> str:
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()
