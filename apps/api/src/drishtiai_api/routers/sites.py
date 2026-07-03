import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from drishtiai_shared.models.site import Site
from drishtiai_shared.models.user import UserRole
from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()


class SiteCreate(BaseModel):
    org_id: uuid.UUID
    name: str
    address: str | None = None
    timezone: str = "Asia/Kathmandu"
    plate_region: str = "NP"


class SitePatch(BaseModel):
    name: str | None = None
    address: str | None = None
    timezone: str | None = None
    plate_region: str | None = None


class SiteOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    address: str | None
    timezone: str
    plate_region: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[SiteOut])
async def list_sites(current_user: CurrentUser, db: DbSession) -> list[Site]:
    q = select(Site)
    if current_user.role not in (UserRole.superadmin,):
        q = q.where(Site.id.in_(current_user.site_ids))
    return list(db.scalars(q).all())


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(body: SiteCreate, current_user: CurrentUser, db: DbSession) -> Site:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    site = Site(
        id=uuid.uuid4(),
        org_id=body.org_id,
        name=body.name,
        address=body.address,
        timezone=body.timezone,
        plate_region=body.plate_region,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(site_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


@router.patch("/{site_id}", response_model=SiteOut)
async def patch_site(
    site_id: uuid.UUID, body: SitePatch, current_user: CurrentUser, db: DbSession
) -> Site:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(site_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    if current_user.role != UserRole.superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin only")
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    db.delete(site)
    db.commit()
