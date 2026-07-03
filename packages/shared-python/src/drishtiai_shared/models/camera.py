import uuid
from datetime import datetime
from enum import Enum as PyEnum

from geoalchemy2 import Geography
from sqlalchemy import String, Boolean, DateTime, ForeignKey, func, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class CameraKind(str, PyEnum):
    ip = "ip"
    analog = "analog"


class CameraRole(str, PyEnum):
    anpr_lane = "anpr_lane"
    parking_entry = "parking_entry"
    parking_exit = "parking_exit"
    parking = "parking"       # legacy / bidirectional
    perimeter = "perimeter"
    general = "general"


class HealthStatus(str, PyEnum):
    online = "online"
    offline = "offline"
    degraded = "degraded"
    unknown = "unknown"


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[CameraKind] = mapped_column(default=CameraKind.ip)
    stream_url: Mapped[str | None] = mapped_column(String(1024))
    resolution_w: Mapped[int | None]
    resolution_h: Mapped[int | None]
    fps: Mapped[float | None]
    gpu_slot: Mapped[int | None]
    role: Mapped[CameraRole] = mapped_column(default=CameraRole.general)
    ptz: Mapped[bool] = mapped_column(Boolean, default=False)
    onvif_profile: Mapped[str | None] = mapped_column(String(64))
    health_status: Mapped[HealthStatus] = mapped_column(default=HealthStatus.unknown)
    geo = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    site: Mapped["Site"] = relationship("Site", back_populates="cameras")  # type: ignore[name-defined]
    zones: Mapped[list["Zone"]] = relationship("Zone", back_populates="camera")  # type: ignore[name-defined]
    events: Mapped[list["Event"]] = relationship("Event", back_populates="camera")  # type: ignore[name-defined]
