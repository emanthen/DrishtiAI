import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from drishtiai_shared.models.camera import Camera, CameraKind, CameraRole, HealthStatus
from drishtiai_shared.models.user import UserRole
from drishtiai_api.deps import CurrentUser, DbSession, require_role

router = APIRouter()


class CameraCreate(BaseModel):
    name: str
    site_id: uuid.UUID
    kind: CameraKind = CameraKind.ip
    stream_url: str | None = None
    role: CameraRole = CameraRole.general
    resolution_w: int | None = None
    resolution_h: int | None = None
    fps: float | None = None


class CameraPatch(BaseModel):
    name: str | None = None
    stream_url: str | None = None
    role: CameraRole | None = None
    enabled: bool | None = None


class CameraOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    kind: CameraKind
    stream_url: str | None
    role: CameraRole
    health_status: HealthStatus
    enabled: bool
    fps: float | None
    resolution_w: int | None
    resolution_h: int | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[CameraOut])
async def list_cameras(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[Camera]:
    q = select(Camera)
    if site_id:
        q = q.where(Camera.site_id == site_id)
    return list(db.scalars(q).all())


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
async def add_camera(
    body: CameraCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> Camera:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    camera = Camera(
        id=uuid.uuid4(),
        site_id=body.site_id,
        name=body.name,
        kind=body.kind,
        stream_url=body.stream_url,
        role=body.role,
        resolution_w=body.resolution_w,
        resolution_h=body.resolution_h,
        fps=body.fps,
        health_status=HealthStatus.unknown,
        enabled=True,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(camera_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return camera


@router.patch("/{camera_id}", response_model=CameraOut)
async def patch_camera(
    camera_id: uuid.UUID,
    body: CameraPatch,
    current_user: CurrentUser,
    db: DbSession,
) -> Camera:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(camera, field, value)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/{camera_id}/health")
async def camera_health(camera_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> dict:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return {
        "camera_id": str(camera_id),
        "name": camera.name,
        "health_status": camera.health_status.value,
        "enabled": camera.enabled,
    }


@router.get("/{camera_id}/live")
async def camera_live_url(camera_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> dict:
    """Return the MJPEG stream URL for this camera (served by the pipeline)."""
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return {
        "camera_id": str(camera_id),
        "mjpeg_url": f"/api/stream/{camera_id}/mjpeg",
    }


@router.post("/discover", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def discover_cameras(current_user: CurrentUser) -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="ONVIF discovery not implemented — Phase 2",
    )
