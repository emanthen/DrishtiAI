"""
Gate controller integration — Phase 4.

Called after every committed plate_read event.
Loads enabled GateRules for the camera, checks the trigger condition,
and fires the matched GateController.

Supported controller kinds:
  webhook  — HTTP POST to a URL (works with any HTTP-capable controller,
             ESP32 relay boards, Hikvision HTTP API, etc.)
  onvif    — SOAP SetRelayOutputState with WS-Security UsernameToken digest
             (Hikvision, Dahua, Axis cameras with built-in relay output)

Both implementations are stdlib-only (urllib) to avoid adding deps.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from drishtiai_shared.models.gate import (
    GateController,
    GateKind,
    GateRule,
    GateTriggerCondition,
    GateTriggerLog,
)
from drishtiai_shared.models.watchlist import WatchlistEntry, Watchlist
from drishtiai_shared.models.access import VisitorPass

log = logging.getLogger(__name__)

_HTTP_TIMEOUT_S = 5


# ── Controller drivers ────────────────────────────────────────────────────────

class _Driver(Protocol):
    def trigger(self, pulse_ms: int) -> None: ...


class _WebhookDriver:
    def __init__(self, config: dict) -> None:
        self._url: str = config["url"]
        self._method: str = config.get("method", "POST").upper()
        self._headers: dict[str, str] = config.get("headers", {})
        self._secret: str | None = config.get("secret")

    def trigger(self, pulse_ms: int) -> None:
        body = f'{{"open": true, "pulse_ms": {pulse_ms}}}'.encode()
        headers = {"Content-Type": "application/json", **self._headers}
        if self._secret:
            headers["X-Gate-Secret"] = self._secret
        req = urllib.request.Request(
            self._url, data=body, headers=headers, method=self._method
        )
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            resp.read()


class _OnvifDriver:
    """
    Fires ONVIF SetRelayOutputState via raw SOAP + WS-Security UsernameToken.
    Compatible with HikVision DS-2CD/DS-K, Dahua IPC, Axis P-series.
    """

    def __init__(self, config: dict) -> None:
        host = config["host"]
        port = int(config.get("port", 80))
        self._url = f"http://{host}:{port}/onvif/device_service"
        self._username: str = config.get("username", "admin")
        self._password: str = config.get("password", "")
        self._relay_token: str = config.get("relay_token", "Token0")

    @staticmethod
    def _wsse_header(username: str, password: str) -> str:
        nonce_raw = secrets.token_bytes(16)
        created = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        digest = base64.b64encode(
            hashlib.sha1(
                nonce_raw + created.encode() + password.encode()
            ).digest()
        ).decode()
        nonce_b64 = base64.b64encode(nonce_raw).decode()
        return (
            "<s:Header>"
            '<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/'
            'oasis-200401-wss-wssecurity-secext-1.0.xsd">'
            "<wsse:UsernameToken>"
            f"<wsse:Username>{username}</wsse:Username>"
            '<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/'
            'oasis-200401-wss-username-token-profile-1.0#PasswordDigest">'
            f"{digest}</wsse:Password>"
            '<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/'
            'oasis-200401-wss-soap-message-security-1.0#Base64Binary">'
            f"{nonce_b64}</wsse:Nonce>"
            '<wsu:Created xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/'
            'oasis-200401-wss-wssecurity-utility-1.0.xsd">'
            f"{created}</wsu:Created>"
            "</wsse:UsernameToken>"
            "</wsse:Security>"
            "</s:Header>"
        )

    def trigger(self, pulse_ms: int) -> None:
        # ONVIF relay output does not natively accept pulse_ms — we activate it;
        # the hardware timer (set in camera firmware) controls the deactivation.
        soap = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
            'xmlns:wsdl="http://www.onvif.org/ver10/device/wsdl">'
            f"{self._wsse_header(self._username, self._password)}"
            "<s:Body>"
            "<wsdl:SetRelayOutputState>"
            f"<wsdl:RelayOutputToken>{self._relay_token}</wsdl:RelayOutputToken>"
            "<wsdl:LogicalState>active</wsdl:LogicalState>"
            "</wsdl:SetRelayOutputState>"
            "</s:Body>"
            "</s:Envelope>"
        )
        req = urllib.request.Request(
            self._url,
            data=soap.encode(),
            headers={
                "Content-Type": 'application/soap+xml; charset=utf-8; action="SetRelayOutputState"',
                "SOAPAction": '"http://www.onvif.org/ver10/device/wsdl/SetRelayOutputState"',
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            resp.read()


def _make_driver(controller: GateController) -> _Driver:
    if controller.kind == GateKind.onvif:
        return _OnvifDriver(controller.config)
    return _WebhookDriver(controller.config)


# ── Condition checks ──────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    return text.upper().replace(" ", "").replace("-", "")


def _check_watchlist(
    db: Session, watchlist_id: uuid.UUID, plate_text: str
) -> bool:
    """Return True if plate_text matches any entry in the watchlist (exact/prefix/fuzzy)."""
    from drishtiai_shared.models.watchlist import PlatePattern
    norm = _normalise(plate_text)
    entries = list(
        db.scalars(
            select(WatchlistEntry).where(WatchlistEntry.watchlist_id == watchlist_id)
        ).all()
    )
    for entry in entries:
        entry_norm = _normalise(entry.plate_text)
        if entry.plate_pattern == PlatePattern.exact and norm == entry_norm:
            return True
        if entry.plate_pattern == PlatePattern.prefix and norm.startswith(entry_norm):
            return True
        if entry.plate_pattern == PlatePattern.fuzzy and entry_norm in norm:
            return True
    return False


def _check_permit(
    db: Session, site_id: uuid.UUID, plate_text: str
) -> "VisitorPass | None":
    """Return the active VisitorPass for this plate, or None."""
    now = datetime.now(tz=timezone.utc)
    norm = _normalise(plate_text)
    return db.scalars(
        select(VisitorPass).where(
            VisitorPass.site_id == site_id,
            VisitorPass.plate == norm,
            VisitorPass.valid_from <= now,
            VisitorPass.valid_to >= now,
            VisitorPass.used == False,  # noqa: E712
        ).limit(1)
    ).first()


# ── Main entry point ──────────────────────────────────────────────────────────

def evaluate_and_trigger(
    *,
    db: Session,
    site_id: uuid.UUID,
    camera_id: uuid.UUID,
    event_id: uuid.UUID,
    plate_text: str,
) -> None:
    """
    Evaluate all enabled GateRules for this camera and fire matching controllers.
    Rules are checked in descending priority order; all matching rules fire.

    Gate safety: if the license is not in an operational state this function
    returns immediately without sending any controller command. The barrier
    hardware then follows its own physical default — DrishtiAI never sends a
    "close" or "lock" command, only "open" pulses.
    """
    from drishtiai_licensing.enforcement import gate_automation_allowed
    if not gate_automation_allowed():
        log.debug(
            "gate: automation disabled (license not operational) — skipping camera=%s plate=%s",
            camera_id, plate_text,
        )
        return

    rules = list(
        db.scalars(
            select(GateRule)
            .where(
                GateRule.camera_id == camera_id,
                GateRule.enabled == True,  # noqa: E712
            )
            .order_by(GateRule.priority.desc())
        ).all()
    )

    for rule in rules:
        controller = db.get(GateController, rule.gate_controller_id)
        if controller is None or not controller.enabled:
            continue

        # Check condition
        matched = False
        matched_pass = None
        cond = rule.trigger_on
        if cond == GateTriggerCondition.any_plate:
            matched = True
        elif cond == GateTriggerCondition.watchlist_match and rule.watchlist_id:
            matched = _check_watchlist(db, rule.watchlist_id, plate_text)
        elif cond == GateTriggerCondition.permit_valid:
            matched_pass = _check_permit(db, site_id, plate_text)
            matched = matched_pass is not None

        if not matched:
            continue

        # Fire the controller
        success = False
        error_msg = None
        try:
            driver = _make_driver(controller)
            driver.trigger(controller.open_pulse_ms)
            success = True
            log.info(
                "gate: triggered controller=%s plate=%s rule=%s",
                controller.name, plate_text, rule.id,
            )
        except Exception as exc:
            error_msg = str(exc)[:500]
            log.warning(
                "gate: trigger failed controller=%s plate=%s error=%s",
                controller.name, plate_text, error_msg,
            )

        # Consume single-use visitor pass after a successful trigger
        if success and matched_pass is not None and matched_pass.single_use:
            matched_pass.used = True
            log.info("gate: consumed single-use pass %s for plate=%s", matched_pass.id, plate_text)

        entry = GateTriggerLog(
            id=uuid.uuid4(),
            gate_rule_id=rule.id,
            gate_controller_id=controller.id,
            event_id=event_id,
            plate_text=plate_text,
            success=success,
            error_msg=error_msg,
        )
        db.add(entry)
        db.commit()
