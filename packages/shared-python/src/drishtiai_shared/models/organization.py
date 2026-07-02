import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class PlanTier(str, PyEnum):
    smb = "smb"
    mid = "mid"
    enterprise = "enterprise"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    plan_tier: Mapped[PlanTier] = mapped_column(default=PlanTier.smb)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sites: Mapped[list["Site"]] = relationship("Site", back_populates="organization")  # type: ignore[name-defined]
    users: Mapped[list["User"]] = relationship("User", back_populates="organization")  # type: ignore[name-defined]
