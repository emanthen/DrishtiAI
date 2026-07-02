import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Float, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drishtiai_shared.db import Base


class VehicleType(str, PyEnum):
    car = "car"
    motorbike = "motorbike"
    scooter = "scooter"
    auto_rickshaw = "auto_rickshaw"
    van = "van"
    suv = "suv"
    truck = "truck"
    bus = "bus"
    other = "other"


class VehicleColor(str, PyEnum):
    white = "white"
    black = "black"
    silver = "silver"
    grey = "grey"
    red = "red"
    blue = "blue"
    green = "green"
    yellow = "yellow"
    orange = "orange"
    brown = "brown"
    maroon = "maroon"
    other = "other"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    type: Mapped[VehicleType | None]
    type_confidence: Mapped[float | None] = mapped_column(Float)
    make: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    make_model_confidence: Mapped[float | None] = mapped_column(Float)
    color: Mapped[VehicleColor | None]
    color_confidence: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plates: Mapped[list["Plate"]] = relationship("Plate", back_populates="vehicle")  # type: ignore[name-defined]
    events: Mapped[list["Event"]] = relationship("Event", back_populates="vehicle")  # type: ignore[name-defined]
