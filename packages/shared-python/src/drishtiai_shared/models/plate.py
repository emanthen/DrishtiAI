import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class PlateFormat(str, PyEnum):
    embossed = "embossed"
    devanagari = "devanagari"
    handwritten = "handwritten"
    unknown = "unknown"


class Plate(Base):
    __tablename__ = "plates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(10))
    format_class: Mapped[PlateFormat] = mapped_column(default=PlateFormat.unknown)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vehicle: Mapped["Vehicle | None"] = relationship("Vehicle", back_populates="plates")  # type: ignore[name-defined]
    events: Mapped[list["Event"]] = relationship("Event", back_populates="plate")  # type: ignore[name-defined]

    __table_args__ = (
        # GIN trigram index for fuzzy/partial plate search — created via Alembic migration
        # because it requires pg_trgm extension
        Index("ix_plates_text_trgm", "text", postgresql_using="gin",
              postgresql_ops={"text": "gin_trgm_ops"}),
    )
