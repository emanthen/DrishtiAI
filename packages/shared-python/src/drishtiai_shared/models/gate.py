import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from drishtiai_shared.db import Base


class GateKind(str, PyEnum):
    webhook = "webhook"
    onvif = "onvif"


class GateTriggerCondition(str, PyEnum):
    any_plate = "any_plate"
    watchlist_match = "watchlist_match"
    permit_valid = "permit_valid"


class GateController(Base):
    __tablename__ = "gate_controllers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[GateKind] = mapped_column(default=GateKind.webhook)
    # webhook: {url, method, headers, secret}
    # onvif:   {host, port, username, password, relay_token}
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    open_pulse_ms: Mapped[int] = mapped_column(Integer, default=500)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GateRule(Base):
    __tablename__ = "gate_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    gate_controller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gate_controllers.id", ondelete="CASCADE")
    )
    trigger_on: Mapped[GateTriggerCondition] = mapped_column(default=GateTriggerCondition.any_plate)
    # required when trigger_on == watchlist_match
    watchlist_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("watchlists.id", ondelete="SET NULL")
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GateTriggerLog(Base):
    __tablename__ = "gate_trigger_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gate_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gate_rules.id", ondelete="SET NULL")
    )
    gate_controller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gate_controllers.id", ondelete="CASCADE")
    )
    # null for manual triggers
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    plate_text: Mapped[str | None] = mapped_column(String(30))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_msg: Mapped[str | None] = mapped_column(String(500))
