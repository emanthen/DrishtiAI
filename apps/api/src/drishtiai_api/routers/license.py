"""
GET /system/license — returns the current license state for the dashboard banner.

Requires authentication. Never exposes PII, plate data, or raw token bytes.
The response is safe to cache for up to 60 seconds (Cache-Control header).
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

import drishtiai_licensing.enforcement as enf
from drishtiai_api.deps import CurrentUser

router = APIRouter()


class LicenseStatusResponse(BaseModel):
    state: str
    message: str
    days_remaining: int | None
    camera_limit: int
    plan_tier: str | None
    client_name: str | None
    expires_at: str | None
    banner: dict | None


@router.get(
    "/license",
    response_model=LicenseStatusResponse,
    summary="Current license state",
    description="Returns the license state, expiry info, and banner data. Safe to poll every 60s.",
)
def get_license_status(_user: CurrentUser) -> LicenseStatusResponse:
    state = enf.get_state()
    claims = enf.get_claims()
    message = enf.get_message()
    banner = enf.expiry_banner()

    return LicenseStatusResponse(
        state=state.value,
        message=message,
        days_remaining=claims.days_until_expiry() if claims else None,
        camera_limit=enf.camera_limit(),
        plan_tier=claims.plan_tier.value if claims else None,
        client_name=claims.client_name if claims else None,
        expires_at=claims.expires_at.isoformat() if claims else None,
        banner=banner,
    )
