import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from drishtiai_shared.db import Base


class WebhookEvent(str, PyEnum):
    plate_read    = "plate_read"
    alert_new     = "alert_new"
    alert_resolved= "alert_resolved"
    gate_trigger  = "gate_trigger"
    camera_offline= "camera_offline"
    parking_open  = "parking_open"
    parking_close = "parking_close"


class Webhook(Base):
    __tablename__ = "webhooks"

    id:      Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name:    Mapped[str]              = mapped_column(String(255), nullable=False)
    url:     Mapped[str]              = mapped_column(String(2048), nullable=False)
    # HMAC-SHA256 signing secret — null means unsigned
    secret:  Mapped[str | None]       = mapped_column(String(256))
    # list of WebhookEvent values to subscribe to; empty = all
    events:  Mapped[list[str]]        = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    enabled: Mapped[bool]             = mapped_column(Boolean, nullable=False, server_default="true")
    created_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_triggered_at:Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_code: Mapped[int | None]      = mapped_column(Integer)
