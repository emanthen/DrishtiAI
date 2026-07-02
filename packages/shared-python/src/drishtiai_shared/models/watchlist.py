import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, func, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class WatchlistCategory(str, PyEnum):
    blocked = "blocked"
    vip = "vip"
    resident = "resident"
    vendor = "vendor"
    staff = "staff"
    police_notice = "police_notice"


class PlatePattern(str, PyEnum):
    exact = "exact"
    prefix = "prefix"
    fuzzy = "fuzzy"


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[WatchlistCategory]
    alert_channels: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site: Mapped["Site"] = relationship("Site", back_populates="watchlists")  # type: ignore[name-defined]
    entries: Mapped[list["WatchlistEntry"]] = relationship("WatchlistEntry", back_populates="watchlist")


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE")
    )
    plate_text: Mapped[str] = mapped_column(String(30), nullable=False)
    plate_pattern: Mapped[PlatePattern] = mapped_column(default=PlatePattern.exact)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    watchlist: Mapped[Watchlist] = relationship("Watchlist", back_populates="entries")
