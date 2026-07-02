import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from drishtiai_shared.db import get_db
from drishtiai_shared.models.user import User, UserRole
from drishtiai_api.auth.tokens import ACCESS_TOKEN_TYPE, decode_token
from drishtiai_api.config import settings

_bearer = HTTPBearer(auto_error=True)

DbSession = Annotated[Session, Depends(get_db)]


async def get_redis() -> aioredis.Redis:
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


RedisClient = Annotated[aioredis.Redis, Depends(get_redis)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: DbSession,
    redis: RedisClient,
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    jti = payload.get("jti", "")
    if jti and await redis.exists(f"token:deny:{jti}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user_id = payload.get("sub")
    user = db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    def _check(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return Depends(_check)
