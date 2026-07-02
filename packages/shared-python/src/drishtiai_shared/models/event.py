import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Float, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class EventKind(str, PyEnum):
    plate_read = "plate_read"
    line_cross = "line_cross"
    wrong_way = "wrong_way"
    illegal_park = "illegal_park"
    helmet_violation = "helmet_violation"
    watchlist_hit = "watchlist_hit"
    gate_open = "gate_open"
    tamper = "tamper"
    congestion = "congestion"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[EventKind] = mapped_column(nullable=False)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    plate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plates.id", ondelete="SET NULL")
    )
    snapshot_key: Mapped[str | None] = mapped_column(String(512))
    clip_key: Mapped[str | None] = mapped_column(String(512))
    confidence: Mapped[float | None] = mapped_column(Float)
    meta_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site: Mapped["Site"] = relationship("Site", back_populates="events")  # type: ignore[name-defined]
    camera: Mapped["Camera"] = relationship("Camera", back_populates="events")  # type: ignore[name-defined]
    vehicle: Mapped["Vehicle | None"] = relationship("Vehicle", back_populates="events")  # type: ignore[name-defined]
    plate: Mapped["Plate | None"] = relationship("Plate", back_populates="events")  # type: ignore[name-defined]
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="event")  # type: ignore[name-defined]

    __table_args__ = (
        Index("ix_events_site_kind_ts", "site_id", "kind", "ts"),
        Index("ix_events_ts", "ts"),
        # Partitioning is declared in Alembic migration 0001, not via SQLAlchemy metadata.
        # SA does not support PARTITION BY in __table_args__ without reflect=True.
    )
