import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class AlertStatus(str, PyEnum):
    new = "new"
    ack = "ack"
    snoozed = "snoozed"
    resolved = "resolved"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    watchlist_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("watchlists.id", ondelete="SET NULL")
    )
    status: Mapped[AlertStatus] = mapped_column(default=AlertStatus.new)
    ack_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="alerts")  # type: ignore[name-defined]
    watchlist: Mapped["Watchlist | None"] = relationship("Watchlist")  # type: ignore[name-defined]
