import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from drishtiai_api.schemas import RequestModel
from sqlalchemy import select

from drishtiai_shared.models.parking import Tariff
from drishtiai_shared.models.user import UserRole
from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class TariffCreate(RequestModel):
    site_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    rules_json: dict
    active: bool = True


class TariffPatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    rules_json: dict | None = None
    active: bool | None = None


class TariffOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    rules_json: dict
    active: bool

    model_config = {"from_attributes": True}


# ── CRUD ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TariffOut])
async def list_tariffs(
    current_user: CurrentUser,
    db: DbSession,
    site_id: uuid.UUID | None = None,
) -> list[Tariff]:
    q = select(Tariff)
    if site_id:
        q = q.where(Tariff.site_id == site_id)
    elif current_user.role != UserRole.superadmin and current_user.site_ids:
        q = q.where(Tariff.site_id.in_(current_user.site_ids))
    return list(db.scalars(q.order_by(Tariff.created_at.desc())).all())


@router.post("", response_model=TariffOut, status_code=status.HTTP_201_CREATED)
async def create_tariff(
    body: TariffCreate, current_user: CurrentUser, db: DbSession
) -> Tariff:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    tariff = Tariff(
        id=uuid.uuid4(),
        site_id=body.site_id,
        name=body.name,
        rules_json=body.rules_json,
        active=body.active,
    )
    db.add(tariff)
    db.commit()
    db.refresh(tariff)
    return tariff


@router.get("/{tariff_id}", response_model=TariffOut)
async def get_tariff(tariff_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Tariff:
    t = db.get(Tariff, tariff_id)
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")
    return t


@router.patch("/{tariff_id}", response_model=TariffOut)
async def patch_tariff(
    tariff_id: uuid.UUID, body: TariffPatch, current_user: CurrentUser, db: DbSession
) -> Tariff:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    t = db.get(Tariff, tariff_id)
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(t, field, value)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{tariff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tariff(
    tariff_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    t = db.get(Tariff, tariff_id)
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")
    db.delete(t)
    db.commit()
