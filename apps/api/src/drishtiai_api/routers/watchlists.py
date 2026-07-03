import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from drishtiai_shared.models.watchlist import (
    Watchlist,
    WatchlistCategory,
    WatchlistEntry,
    PlatePattern,
)
from drishtiai_shared.models.user import UserRole
from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class WatchlistCreate(BaseModel):
    site_id: uuid.UUID
    name: str
    category: WatchlistCategory
    alert_channels: list[str] = []


class WatchlistPatch(BaseModel):
    name: str | None = None
    category: WatchlistCategory | None = None
    alert_channels: list[str] | None = None


class WatchlistOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    category: WatchlistCategory
    alert_channels: list[str]

    model_config = {"from_attributes": True}


class EntryCreate(BaseModel):
    plate_text: str
    plate_pattern: PlatePattern = PlatePattern.exact
    notes: str | None = None


class EntryOut(BaseModel):
    id: uuid.UUID
    watchlist_id: uuid.UUID
    plate_text: str
    plate_pattern: PlatePattern
    notes: str | None

    model_config = {"from_attributes": True}


# ── Watchlist CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[WatchlistOut])
async def list_watchlists(
    current_user: CurrentUser,
    db: DbSession,
    site_id: uuid.UUID | None = None,
) -> list[Watchlist]:
    q = select(Watchlist)
    if site_id:
        q = q.where(Watchlist.site_id == site_id)
    elif current_user.role != UserRole.superadmin and current_user.site_ids:
        q = q.where(Watchlist.site_id.in_(current_user.site_ids))
    return list(db.scalars(q).all())


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    body: WatchlistCreate, current_user: CurrentUser, db: DbSession
) -> Watchlist:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin, UserRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    wl = Watchlist(
        id=uuid.uuid4(),
        site_id=body.site_id,
        name=body.name,
        category=body.category,
        alert_channels=body.alert_channels,
    )
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


@router.get("/{watchlist_id}", response_model=WatchlistOut)
async def get_watchlist(
    watchlist_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Watchlist:
    wl = db.get(Watchlist, watchlist_id)
    if wl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    return wl


@router.patch("/{watchlist_id}", response_model=WatchlistOut)
async def patch_watchlist(
    watchlist_id: uuid.UUID, body: WatchlistPatch, current_user: CurrentUser, db: DbSession
) -> Watchlist:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin, UserRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    wl = db.get(Watchlist, watchlist_id)
    if wl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(wl, field, value)
    db.commit()
    db.refresh(wl)
    return wl


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    wl = db.get(Watchlist, watchlist_id)
    if wl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    db.delete(wl)
    db.commit()


# ── Entry CRUD ─────────────────────────────────────────────────────────────────

@router.get("/{watchlist_id}/entries", response_model=list[EntryOut])
async def list_entries(
    watchlist_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> list[WatchlistEntry]:
    if db.get(Watchlist, watchlist_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    return list(
        db.scalars(
            select(WatchlistEntry).where(WatchlistEntry.watchlist_id == watchlist_id)
        ).all()
    )


@router.post(
    "/{watchlist_id}/entries",
    response_model=EntryOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_entry(
    watchlist_id: uuid.UUID, body: EntryCreate, current_user: CurrentUser, db: DbSession
) -> WatchlistEntry:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin, UserRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if db.get(Watchlist, watchlist_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    entry = WatchlistEntry(
        id=uuid.uuid4(),
        watchlist_id=watchlist_id,
        plate_text=body.plate_text.upper().strip(),
        plate_pattern=body.plate_pattern,
        notes=body.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete(
    "/{watchlist_id}/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_entry(
    watchlist_id: uuid.UUID,
    entry_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin, UserRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    entry = db.get(WatchlistEntry, entry_id)
    if entry is None or entry.watchlist_id != watchlist_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    db.delete(entry)
    db.commit()
