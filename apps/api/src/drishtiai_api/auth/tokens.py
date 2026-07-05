import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt  # noqa: F401 (JWTError re-exported for callers)

from drishtiai_api.config import settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
_ALGORITHM = "RS256"


def _private_key() -> str:
    key = settings.jwt_private_key_pem
    if not key:
        raise RuntimeError(
            "JWT_PRIVATE_KEY_PEM is not set. Run 'make keygen' to generate a keypair "
            "and add the result to your .env file."
        )
    return key


def _public_key() -> str:
    key = settings.jwt_public_key_pem
    if not key:
        raise RuntimeError(
            "JWT_PUBLIC_KEY_PEM is not set. Run 'make keygen' to generate a keypair "
            "and add the result to your .env file."
        )
    return key


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(user_id: str, role: str) -> str:
    expire = _now() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _private_key(), algorithm=_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = _now() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "type": REFRESH_TOKEN_TYPE,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _private_key(), algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a token. Raises JWTError on failure."""
    return jwt.decode(token, _public_key(), algorithms=[_ALGORITHM])
