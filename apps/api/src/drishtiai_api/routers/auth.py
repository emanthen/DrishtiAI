import hashlib
import time
import uuid
from datetime import timedelta, timezone, datetime

from fastapi import APIRouter, HTTPException, Request, status
from jose import JWTError
from pydantic import BaseModel, EmailStr, Field, SecretStr
from drishtiai_api.schemas import RequestModel
from sqlalchemy import select, update

from drishtiai_shared.models.user import User
from drishtiai_shared.models.refresh_token import RefreshTokenHash
from drishtiai_api.audit import log_action
from drishtiai_api.auth import lockout as lockout_svc
from drishtiai_api.auth import totp as totp_auth
from drishtiai_api.auth.password import DUMMY_HASH, verify_password
from drishtiai_api.auth.tokens import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from drishtiai_api.config import settings
from drishtiai_api.deps import CurrentUser, DbSession, RedisClient
from drishtiai_api.limiter import limiter
from drishtiai_api.metrics import auth_failures_total, totp_failures_total

router = APIRouter()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginRequest(RequestModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=1024)
    totp_code: str | None = Field(default=None, min_length=6, max_length=6, pattern=r"^\d{6}$")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(RequestModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


def _store_refresh_token(db, token: str, user_id: uuid.UUID, expires_days: int) -> None:
    payload = decode_token(token)
    jti = payload["jti"]
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=expires_days)
    db.add(RefreshTokenHash(
        id=uuid.uuid4(),
        jti=jti,
        user_id=user_id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
    ))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute;10/hour")
async def login(body: LoginRequest, request: Request, db: DbSession, redis: RedisClient) -> TokenResponse:
    client_ip = request.client.host if request.client else None
    user = db.scalar(select(User).where(User.email == body.email))

    # Always run the hash to equalise timing across user-found / not-found paths.
    pw_ok = verify_password(body.password.get_secret_value(), user.password_hash if user else DUMMY_HASH)

    # Check account-level lockout (after hash to preserve timing).
    if user and await lockout_svc.is_locked(redis, str(user.id)):
        auth_failures_total.labels(reason="locked").inc()
        log_action(db, actor_id=user.id, action="user.login_locked",
                   target_type="user", target_id=str(user.id), ip=client_ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user is None or not pw_ok or not user.is_active:
        if user:
            await lockout_svc.on_login_failure(redis, str(user.id))
            reason = "bad_password" if pw_ok is False else "account_inactive"
        else:
            reason = "unknown_user"
        auth_failures_total.labels(reason=reason).inc()
        log_action(db, actor_id=user.id if user else None,
                   action="user.login_failed",
                   target_type="user", target_id=body.email,
                   ip=client_ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # TOTP check — only for superadmin + site_admin who have it configured.
    if user.totp_enabled and user.mfa_secret:
        if not body.totp_code or not totp_auth.verify_code(user.mfa_secret, body.totp_code):
            await lockout_svc.on_login_failure(redis, str(user.id))
            totp_failures_total.inc()
            auth_failures_total.labels(reason="totp").inc()
            log_action(db, actor_id=user.id, action="user.login_mfa_failed",
                       target_type="user", target_id=str(user.id), ip=client_ip)
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await lockout_svc.on_login_success(redis, str(user.id))
    log_action(db, actor_id=user.id, action="user.login_success",
               target_type="user", target_id=str(user.id), ip=client_ip)
    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))
    _store_refresh_token(db, refresh_token, user.id, settings.jwt_refresh_token_expire_days)
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(body: RefreshRequest, request: Request, db: DbSession, redis: RedisClient) -> TokenResponse:
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    jti = payload.get("jti", "")

    record = db.scalar(select(RefreshTokenHash).where(RefreshTokenHash.jti == jti))
    if (record is None
            or record.revoked
            or record.token_hash != _hash_token(body.refresh_token)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    record.revoked = True

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(str(user.id), user.role.value)
    new_refresh = create_refresh_token(str(user.id))
    _store_refresh_token(db, new_refresh, user.id, settings.jwt_refresh_token_expire_days)
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUser, request: Request, db: DbSession, redis: RedisClient) -> None:
    # Denylist the current access token (immediate revocation, not just 15-min expiry).
    jti = getattr(request.state, "token_jti", None)
    exp = getattr(request.state, "token_exp", 0)
    if jti:
        remaining = max(0, int(exp) - int(time.time()))
        if remaining > 0:
            await redis.setex(f"token:deny:{jti}", remaining, "1")

    # Revoke all active refresh tokens for this user.
    db.execute(
        update(RefreshTokenHash)
        .where(RefreshTokenHash.user_id == current_user.id, RefreshTokenHash.revoked.is_(False))
        .values(revoked=True)
    )
    log_action(db, actor_id=current_user.id, action="user.logout",
               target_type="user", target_id=str(current_user.id))
    db.commit()


@router.get("/me")
async def me(current_user: CurrentUser) -> dict:
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role.value,
        "totp_enabled": current_user.totp_enabled,
    }
