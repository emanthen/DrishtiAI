import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class DataClass(str, PyEnum):
    snapshots = "snapshots"
    clips = "clips"
    continuous_recording = "continuous_recording"
    plate_events = "plate_events"
    audit_logs = "audit_logs"


class RetentionPolicy(Base):
    __tablename__ = "retention_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    data_class: Mapped[DataClass] = mapped_column(nullable=False)
    retain_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    site: Mapped["Site"] = relationship("Site", back_populates="retention_policies")  # type: ignore[name-defined]
