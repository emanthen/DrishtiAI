import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class ZonePurpose(str, PyEnum):
    entry = "entry"
    exit = "exit"
    parking = "parking"
    no_park = "no_park"
    wrong_way = "wrong_way"
    line_count = "line_count"
    perimeter = "perimeter"


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[ZonePurpose]
    geometry_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    camera: Mapped["Camera"] = relationship("Camera", back_populates="zones")  # type: ignore[name-defined]
    site: Mapped["Site"] = relationship("Site", back_populates="zones")  # type: ignore[name-defined]
