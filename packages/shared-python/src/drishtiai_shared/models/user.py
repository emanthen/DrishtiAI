import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class UserRole(str, PyEnum):
    superadmin = "superadmin"
    site_admin = "site_admin"
    manager = "manager"
    guard = "guard"
    resident = "resident"
    auditor = "auditor"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    site_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")  # type: ignore[name-defined]
