"""
Webhook management endpoints.

Authenticated site_admin+ can register outbound webhook URLs that DrishtiAI
will POST to when specific events occur.  Webhooks are signed with HMAC-SHA256
when a secret is supplied.

Supported event types (matches WebhookEvent enum in shared models):
  plate_read | alert_new | alert_resolved | gate_trigger |
  camera_offline | parking_open | parking_close
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from drishtiai_api.schemas import RequestModel
from sqlalchemy import select, update

from drishtiai_shared.models.webhook import Webhook, WebhookEvent
from ..deps import CurrentUser, DbSession
from ..http_safe import assert_public_url

router = APIRouter()

_TIMEOUT_S = 5


# ── Schemas ───────────────────────────────────────────────────────────────────

class WebhookCreate(RequestModel):
    site_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)
    secret: str | None = Field(default=None, max_length=256)
    events: list[WebhookEvent] = Field(default_factory=list, max_length=20)


class WebhookUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    secret: str | None = Field(default=None, max_length=256)
    events: list[WebhookEvent] | None = Field(default=None, max_length=20)
    enabled: bool | None = None


class WebhookOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    url: str
    has_secret: bool
    events: list[str]
    enabled: bool
    created_at: datetime
    last_triggered_at: datetime | None
    last_status_code: int | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, wh: Webhook) -> "WebhookOut":
        return cls(
            id=wh.id,
            site_id=wh.site_id,
            name=wh.name,
            url=wh.url,
            has_secret=wh.secret is not None,
            events=wh.events or [],
            enabled=wh.enabled,
            created_at=wh.created_at,
            last_triggered_at=wh.last_triggered_at,
            last_status_code=wh.last_status_code,
        )


class TestResult(BaseModel):
    url: str
    status_code: int | None
    ok: bool
    error: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_site_access(current_user, site_id: uuid.UUID) -> None:
    from drishtiai_shared.models.user import UserRole
    if current_user.role == UserRole.superadmin:
        return
    if str(site_id) not in (current_user.site_ids or []):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No access to this site")


def _sign(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _deliver(wh: Webhook, body: bytes) -> TestResult:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DrishtiAI-Webhook/1.0",
        "X-Drishti-Event-ID": str(uuid.uuid4()),
    }
    if wh.secret:
        headers["X-Drishti-Signature"] = _sign(wh.secret, body)
    try:
        req = urllib.request.Request(wh.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return TestResult(url=wh.url, status_code=resp.status, ok=True)
    except urllib.error.HTTPError as exc:
        return TestResult(url=wh.url, status_code=exc.code, ok=False,
                          error=f"HTTP {exc.code}")
    except Exception as exc:
        return TestResult(url=wh.url, status_code=None, ok=False, error=str(exc))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[WebhookOut])
async def list_webhooks(
    current_user: CurrentUser,
    db: DbSession,
    site_id: uuid.UUID | None = None,
):
    from drishtiai_shared.models.user import UserRole
    q = select(Webhook)
    if current_user.role != UserRole.superadmin:
        allowed = current_user.site_ids or []
        if site_id and str(site_id) not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        if site_id:
            q = q.where(Webhook.site_id == site_id)
        else:
            q = q.where(Webhook.site_id.in_(allowed))
    elif site_id:
        q = q.where(Webhook.site_id == site_id)
    rows = db.scalars(q.order_by(Webhook.created_at)).all()
    return [WebhookOut.from_orm(r) for r in rows]


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    current_user: CurrentUser,
    db: DbSession,
):
    _assert_site_access(current_user, body.site_id)
    assert_public_url(body.url)
    wh = Webhook(
        id=uuid.uuid4(),
        site_id=body.site_id,
        name=body.name,
        url=body.url,
        secret=body.secret,
        events=[e.value for e in body.events],
        enabled=True,
    )
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return WebhookOut.from_orm(wh)


@router.get("/{webhook_id}", response_model=WebhookOut)
async def get_webhook(
    webhook_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
):
    wh = db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    _assert_site_access(current_user, wh.site_id)
    return WebhookOut.from_orm(wh)


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def update_webhook(
    webhook_id: uuid.UUID,
    body: WebhookUpdate,
    current_user: CurrentUser,
    db: DbSession,
):
    wh = db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    _assert_site_access(current_user, wh.site_id)
    if body.name    is not None: wh.name    = body.name
    if body.url     is not None:
        assert_public_url(body.url)
        wh.url = body.url
    if body.secret  is not None: wh.secret  = body.secret
    if body.events  is not None: wh.events  = [e.value for e in body.events]
    if body.enabled is not None: wh.enabled = body.enabled
    db.commit()
    db.refresh(wh)
    return WebhookOut.from_orm(wh)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
):
    wh = db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    _assert_site_access(current_user, wh.site_id)
    db.delete(wh)
    db.commit()


@router.post("/{webhook_id}/test", response_model=TestResult)
async def test_webhook(
    webhook_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
):
    """Send a synthetic ping payload to the webhook URL and return the HTTP result."""
    wh = db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    _assert_site_access(current_user, wh.site_id)

    body = json.dumps({
        "event": "ping",
        "site_id": str(wh.site_id),
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "message": "DrishtiAI webhook test",
    }).encode()

    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _deliver, wh, body)

    # Record the test attempt
    db.execute(
        update(Webhook)
        .where(Webhook.id == wh.id)
        .values(
            last_triggered_at=datetime.now(tz=timezone.utc),
            last_status_code=result.status_code,
        )
    )
    db.commit()
    return result
