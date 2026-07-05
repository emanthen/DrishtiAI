import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from drishtiai_shared.models.vehicle import Vehicle, VehicleColor, VehicleType
from drishtiai_shared.models.plate import Plate
from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()


class PlateRef(BaseModel):
    id: uuid.UUID
    text: str
    format_class: str

    model_config = {"from_attributes": True}


class VehicleOut(BaseModel):
    id: uuid.UUID
    type: str | None
    type_confidence: float | None
    color: str | None
    color_confidence: float | None
    make: str | None
    model: str | None
    first_seen: datetime | None
    last_seen: datetime | None
    plates: list[PlateRef] = []

    model_config = {"from_attributes": True}


@router.get("", response_model=list[VehicleOut])
async def list_vehicles(
    current_user: CurrentUser,
    db: DbSession,
    color: Annotated[VehicleColor | None, Query()] = None,
    vehicle_type: Annotated[VehicleType | None, Query(alias="type")] = None,
    plate: Annotated[str | None, Query(description="Partial plate text (trigram)")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Vehicle]:
    q = select(Vehicle).options(joinedload(Vehicle.plates)).order_by(Vehicle.last_seen.desc())

    if color:
        q = q.where(Vehicle.color == color.value)
    if vehicle_type:
        q = q.where(Vehicle.type == vehicle_type.value)
    if plate:
        q = q.join(Vehicle.plates).where(Plate.text.op("%%")(plate))

    q = q.limit(limit)
    return list(db.scalars(q).unique().all())


@router.get("/{vehicle_id}", response_model=VehicleOut)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Vehicle:
    vehicle = db.scalar(
        select(Vehicle)
        .options(joinedload(Vehicle.plates))
        .where(Vehicle.id == vehicle_id)
    )
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return vehicle


@router.post("/{vehicle_id}/detect-type", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def detect_vehicle_type(vehicle_id: uuid.UUID, current_user: CurrentUser) -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Vehicle type detection requires RT-DETR model weights — not yet integrated",
    )
