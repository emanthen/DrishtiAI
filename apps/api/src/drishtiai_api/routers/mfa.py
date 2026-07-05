"""MFA management endpoints — TOTP setup, confirm, and disable."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from drishtiai_api.auth import totp as totp_auth
from drishtiai_api.deps import CurrentUser, DbSession, RedisClient

router = APIRouter()

_SETUP_TTL = 600  # 10 minutes for the interim setup secret


class MFASetupResponse(BaseModel):
    provisioning_uri: str
    secret: str  # shown once — user must save this for recovery


class MFAConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MFADisableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.post("/setup", response_model=MFASetupResponse)
async def mfa_setup(current_user: CurrentUser, redis: RedisClient) -> MFASetupResponse:
    """Generate a new TOTP secret and provisioning URI.

    The secret is stored in Redis for 10 minutes pending confirmation.
    It is NOT written to the DB until /mfa/confirm succeeds.
    """
    secret = totp_auth.generate_secret()
    uri = totp_auth.get_provisioning_uri(secret, current_user.email)
    await redis.setex(f"totp:setup:{current_user.id}", _SETUP_TTL, secret)
    return MFASetupResponse(provisioning_uri=uri, secret=secret)


@router.post("/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_confirm(
    body: MFAConfirmRequest,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
) -> None:
    """Verify the first TOTP code and enable MFA on the account."""
    secret = await redis.get(f"totp:setup:{current_user.id}")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup session expired — restart setup",
        )
    if not totp_auth.verify_code(secret, body.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

    current_user.mfa_secret = secret
    current_user.totp_enabled = True
    db.commit()
    await redis.delete(f"totp:setup:{current_user.id}")


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_disable(
    body: MFADisableRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Disable MFA after verifying a valid TOTP code."""
    if not current_user.totp_enabled or not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled on this account",
        )
    if not totp_auth.verify_code(current_user.mfa_secret, body.code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid code")

    current_user.mfa_secret = None
    current_user.totp_enabled = False
    db.commit()
