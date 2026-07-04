import base64
import hashlib
import secrets
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from drishtiai_api.schemas import RequestModel
from sqlalchemy import select

from drishtiai_shared.models.gate import (
    GateController,
    GateKind,
    GateRule,
    GateTriggerCondition,
    GateTriggerLog,
)
from drishtiai_shared.models.user import UserRole
from drishtiai_api.config import settings
from drishtiai_api.deps import CurrentUser, DbSession
from drishtiai_api.gate_creds import decrypt_config, encrypt_config, redact_config

router = APIRouter()

_HTTP_TIMEOUT_S = 5


def _fire_controller(gc: GateController) -> None:
    """Send an open command to a gate controller (webhook or ONVIF)."""
    if gc.kind == GateKind.onvif:
        cfg = decrypt_config(gc.config, settings.gate_credential_key)
        host, port = cfg["host"], int(cfg.get("port", 80))
        username, password = cfg.get("username", "admin"), cfg.get("password", "")
        relay_token = cfg.get("relay_token", "Token0")
        nonce_raw = secrets.token_bytes(16)
        created = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        digest = base64.b64encode(
            hashlib.sha1(nonce_raw + created.encode() + password.encode()).digest()
        ).decode()
        nonce_b64 = base64.b64encode(nonce_raw).decode()
        soap = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
            'xmlns:wsdl="http://www.onvif.org/ver10/device/wsdl">'
            "<s:Header>"
            '<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
            f"<wsse:UsernameToken><wsse:Username>{username}</wsse:Username>"
            '<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">'
            f"{digest}</wsse:Password>"
            f'<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce_b64}</wsse:Nonce>'
            f'<wsu:Created xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">{created}</wsu:Created>'
            "</wsse:UsernameToken></wsse:Security></s:Header>"
            "<s:Body><wsdl:SetRelayOutputState>"
            f"<wsdl:RelayOutputToken>{relay_token}</wsdl:RelayOutputToken>"
            "<wsdl:LogicalState>active</wsdl:LogicalState>"
            "</wsdl:SetRelayOutputState></s:Body></s:Envelope>"
        )
        req = urllib.request.Request(
            f"http://{host}:{port}/onvif/device_service",
            data=soap.encode(),
            headers={"Content-Type": 'application/soap+xml; charset=utf-8'},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            resp.read()
    else:
        cfg = decrypt_config(gc.config, settings.gate_credential_key)
        url: str = cfg["url"]
        method: str = cfg.get("method", "POST").upper()
        headers: dict = {"Content-Type": "application/json", **cfg.get("headers", {})}
        if cfg.get("secret"):
            headers["X-Gate-Secret"] = cfg["secret"]
        body = f'{{"open": true, "pulse_ms": {gc.open_pulse_ms}}}'.encode()
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            resp.read()


# ── Schemas ────────────────────────────────────────────────────────────────────

class GateControllerCreate(RequestModel):
    site_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    kind: GateKind = GateKind.webhook
    config: dict = Field(default_factory=dict)
    open_pulse_ms: int = Field(default=500, ge=100, le=30000)


class GateControllerPatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: GateKind | None = None
    config: dict | None = None
    open_pulse_ms: int | None = Field(default=None, ge=100, le=30000)
    enabled: bool | None = None


class GateControllerOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    kind: GateKind
    config: dict
    open_pulse_ms: int
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GateRuleCreate(RequestModel):
    camera_id: uuid.UUID
    gate_controller_id: uuid.UUID
    trigger_on: GateTriggerCondition = GateTriggerCondition.any_plate
    watchlist_id: uuid.UUID | None = None
    priority: int = Field(default=0, ge=0, le=1000)


class GateRulePatch(RequestModel):
    trigger_on: GateTriggerCondition | None = None
    watchlist_id: uuid.UUID | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    enabled: bool | None = None


class GateRuleOut(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    gate_controller_id: uuid.UUID
    trigger_on: GateTriggerCondition
    watchlist_id: uuid.UUID | None
    priority: int
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GateTriggerLogOut(BaseModel):
    id: uuid.UUID
    gate_rule_id: uuid.UUID | None
    gate_controller_id: uuid.UUID
    event_id: uuid.UUID | None
    plate_text: str | None
    triggered_at: datetime
    success: bool
    error_msg: str | None

    model_config = {"from_attributes": True}


# ── Gate controllers ───────────────────────────────────────────────────────────

def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def _to_out(gc: GateController) -> GateControllerOut:
    """Return GateControllerOut with sensitive config fields redacted."""
    return GateControllerOut(
        id=gc.id,
        site_id=gc.site_id,
        name=gc.name,
        kind=gc.kind,
        config=redact_config(gc.config),
        open_pulse_ms=gc.open_pulse_ms,
        enabled=gc.enabled,
        created_at=gc.created_at,
    )


@router.get("/controllers", response_model=list[GateControllerOut])
async def list_controllers(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[GateControllerOut]:
    q = select(GateController)
    if site_id:
        q = q.where(GateController.site_id == site_id)
    elif current_user.role != UserRole.superadmin and current_user.site_ids:
        q = q.where(GateController.site_id.in_(current_user.site_ids))
    return [_to_out(gc) for gc in db.scalars(q.order_by(GateController.created_at)).all()]


@router.post("/controllers", response_model=GateControllerOut, status_code=status.HTTP_201_CREATED)
async def create_controller(
    body: GateControllerCreate, current_user: CurrentUser, db: DbSession
) -> GateControllerOut:
    _require_admin(current_user)
    gc = GateController(
        id=uuid.uuid4(),
        site_id=body.site_id,
        name=body.name,
        kind=body.kind,
        config=encrypt_config(body.config, settings.gate_credential_key),
        open_pulse_ms=body.open_pulse_ms,
    )
    db.add(gc)
    db.commit()
    db.refresh(gc)
    return _to_out(gc)


@router.get("/controllers/{controller_id}", response_model=GateControllerOut)
async def get_controller(
    controller_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> GateControllerOut:
    gc = db.get(GateController, controller_id)
    if gc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
    return _to_out(gc)


@router.patch("/controllers/{controller_id}", response_model=GateControllerOut)
async def patch_controller(
    controller_id: uuid.UUID, body: GateControllerPatch, current_user: CurrentUser, db: DbSession
) -> GateControllerOut:
    _require_admin(current_user)
    gc = db.get(GateController, controller_id)
    if gc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
    patch_data = body.model_dump(exclude_none=True)
    if "config" in patch_data:
        patch_data["config"] = encrypt_config(patch_data["config"], settings.gate_credential_key)
    for field, value in patch_data.items():
        setattr(gc, field, value)
    db.commit()
    db.refresh(gc)
    return _to_out(gc)


@router.delete("/controllers/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_controller(
    controller_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    _require_admin(current_user)
    gc = db.get(GateController, controller_id)
    if gc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
    db.delete(gc)
    db.commit()


@router.post("/controllers/{controller_id}/trigger", response_model=GateTriggerLogOut)
async def manual_trigger(
    controller_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> GateTriggerLog:
    """Manually open a gate — bypasses all rules."""
    import asyncio

    gc = db.get(GateController, controller_id)
    if gc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller not found")
    if not gc.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Controller is disabled")

    success = False
    error_msg = None
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _fire_controller, gc)
        success = True
    except Exception as exc:
        error_msg = str(exc)[:500]

    log_entry = GateTriggerLog(
        id=uuid.uuid4(),
        gate_controller_id=gc.id,
        success=success,
        error_msg=error_msg,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gate trigger failed: {error_msg}",
        )
    return log_entry


@router.get("/controllers/{controller_id}/log", response_model=list[GateTriggerLogOut])
async def controller_log(
    controller_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[GateTriggerLog]:
    return list(
        db.scalars(
            select(GateTriggerLog)
            .where(GateTriggerLog.gate_controller_id == controller_id)
            .order_by(GateTriggerLog.triggered_at.desc())
            .limit(limit)
        ).all()
    )


# ── Gate rules ────────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[GateRuleOut])
async def list_rules(
    current_user: CurrentUser,
    db: DbSession,
    camera_id: Annotated[uuid.UUID | None, Query()] = None,
    controller_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[GateRule]:
    q = select(GateRule)
    if camera_id:
        q = q.where(GateRule.camera_id == camera_id)
    if controller_id:
        q = q.where(GateRule.gate_controller_id == controller_id)
    return list(db.scalars(q.order_by(GateRule.priority.desc())).all())


@router.post("/rules", response_model=GateRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: GateRuleCreate, current_user: CurrentUser, db: DbSession
) -> GateRule:
    _require_admin(current_user)
    if body.trigger_on == GateTriggerCondition.watchlist_match and body.watchlist_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="watchlist_id required when trigger_on=watchlist_match",
        )
    rule = GateRule(
        id=uuid.uuid4(),
        camera_id=body.camera_id,
        gate_controller_id=body.gate_controller_id,
        trigger_on=body.trigger_on,
        watchlist_id=body.watchlist_id,
        priority=body.priority,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=GateRuleOut)
async def patch_rule(
    rule_id: uuid.UUID, body: GateRulePatch, current_user: CurrentUser, db: DbSession
) -> GateRule:
    _require_admin(current_user)
    rule = db.get(GateRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    _require_admin(current_user)
    rule = db.get(GateRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    db.commit()
