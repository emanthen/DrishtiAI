import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    geo = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kathmandu")
    plate_region: Mapped[str] = mapped_column(String(10), default="NP")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="sites")  # type: ignore[name-defined]
    cameras: Mapped[list["Camera"]] = relationship("Camera", back_populates="site")  # type: ignore[name-defined]
    zones: Mapped[list["Zone"]] = relationship("Zone", back_populates="site")  # type: ignore[name-defined]
    events: Mapped[list["Event"]] = relationship("Event", back_populates="site")  # type: ignore[name-defined]
    watchlists: Mapped[list["Watchlist"]] = relationship("Watchlist", back_populates="site")  # type: ignore[name-defined]
    retention_policies: Mapped[list["RetentionPolicy"]] = relationship("RetentionPolicy", back_populates="site")  # type: ignore[name-defined]
