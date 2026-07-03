import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func

from drishtiai_shared.models.access import VisitorPass
from drishtiai_shared.models.user import UserRole
from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class VisitorPassCreate(BaseModel):
    site_id: uuid.UUID | None = None
    plate: str
    valid_from: datetime
    valid_to: datetime
    single_use: bool = True
    notes: str | None = None

    @field_validator("plate")
    @classmethod
    def normalise_plate(cls, v: str) -> str:
        return v.upper().strip().replace(" ", "").replace("-", "")

    @field_validator("valid_to")
    @classmethod
    def validate_window(cls, v: datetime, info) -> datetime:
        valid_from = info.data.get("valid_from")
        if valid_from and v <= valid_from:
            raise ValueError("valid_to must be after valid_from")
        return v


class VisitorPassOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    host_user_id: uuid.UUID | None
    plate: str
    valid_from: datetime
    valid_to: datetime
    single_use: bool
    used: bool
    notes: str | None
    created_at: datetime
    # computed
    pass_status: str = "unknown"

    model_config = {"from_attributes": True}


class VisitorPassPage(BaseModel):
    items: list[VisitorPassOut]
    total: int
    next_cursor: str | None


def _status(p: VisitorPass) -> str:
    if p.used:
        return "used"
    now = datetime.now(tz=timezone.utc)
    if p.valid_from > now:
        return "upcoming"
    if p.valid_to < now:
        return "expired"
    return "active"


def _enrich(p: VisitorPass) -> VisitorPassOut:
    out = VisitorPassOut.model_validate(p)
    out.pass_status = _status(p)
    return out


def _get_or_404(pass_id: uuid.UUID, db: DbSession) -> VisitorPass:
    p = db.get(VisitorPass, pass_id)
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor pass not found")
    return p


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/mine", response_model=list[VisitorPassOut])
async def list_my_passes(
    current_user: CurrentUser,
    db: DbSession,
    pass_status: Annotated[str | None, Query(alias="status")] = None,
) -> list[VisitorPassOut]:
    """Current user's own visitor passes."""
    q = select(VisitorPass).where(VisitorPass.host_user_id == current_user.id)
    q = _apply_status_filter(q, pass_status)
    passes = list(db.scalars(q.order_by(VisitorPass.valid_from.desc())).all())
    return [_enrich(p) for p in passes]


@router.get("", response_model=VisitorPassPage)
async def list_passes(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    host_user_id: Annotated[uuid.UUID | None, Query()] = None,
    pass_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> VisitorPassPage:
    q = select(VisitorPass)
    if site_id:
        q = q.where(VisitorPass.site_id == site_id)
    elif current_user.role != UserRole.superadmin and current_user.site_ids:
        q = q.where(VisitorPass.site_id.in_(current_user.site_ids))
    if host_user_id:
        q = q.where(VisitorPass.host_user_id == host_user_id)
    q = _apply_status_filter(q, pass_status)
    if cursor:
        try:
            q = q.where(VisitorPass.valid_from < datetime.fromisoformat(cursor))
        except ValueError:
            pass

    q = q.order_by(VisitorPass.valid_from.desc()).limit(limit + 1)
    rows = list(db.scalars(q).all())
    items = [_enrich(p) for p in rows[:limit]]
    next_cursor = items[-1].valid_from.isoformat() if len(rows) > limit else None
    total = db.scalar(select(func.count(VisitorPass.id))) or 0
    return VisitorPassPage(items=items, total=total, next_cursor=next_cursor)


@router.post("", response_model=VisitorPassOut, status_code=status.HTTP_201_CREATED)
async def create_pass(
    body: VisitorPassCreate, current_user: CurrentUser, db: DbSession
) -> VisitorPassOut:
    site_id = body.site_id
    if site_id is None:
        if not current_user.site_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="site_id required")
        site_id = uuid.UUID(current_user.site_ids[0])
    p = VisitorPass(
        id=uuid.uuid4(),
        site_id=site_id,
        host_user_id=current_user.id,
        plate=body.plate,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        single_use=body.single_use,
        used=False,
        notes=body.notes,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _enrich(p)


@router.get("/{pass_id}", response_model=VisitorPassOut)
async def get_pass(
    pass_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> VisitorPassOut:
    return _enrich(_get_or_404(pass_id, db))


@router.delete("/{pass_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_pass(
    pass_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    p = _get_or_404(pass_id, db)
    # Only the host or admins can cancel
    is_admin = current_user.role in (UserRole.superadmin, UserRole.site_admin)
    if not is_admin and p.host_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your pass")
    db.delete(p)
    db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_status_filter(q, pass_status: str | None):
    now = datetime.now(tz=timezone.utc)
    if pass_status == "active":
        q = q.where(VisitorPass.valid_from <= now, VisitorPass.valid_to >= now, VisitorPass.used == False)  # noqa: E712
    elif pass_status == "upcoming":
        q = q.where(VisitorPass.valid_from > now)
    elif pass_status == "expired":
        q = q.where(VisitorPass.valid_to < now)
    elif pass_status == "used":
        q = q.where(VisitorPass.used == True)  # noqa: E712
    return q
