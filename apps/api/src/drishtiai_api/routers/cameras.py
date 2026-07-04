import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func

from drishtiai_shared.models.camera import Camera, CameraKind, CameraRole, HealthStatus
from drishtiai_shared.models.user import UserRole
from drishtiai_api.deps import CurrentUser, DbSession, RedisClient, require_role
from drishtiai_api.schemas import RequestModel
from drishtiai_api.sanitize import strip_html

router = APIRouter()

_RTSP_SCHEMES = ("rtsp://", "rtsps://")


class CameraCreate(RequestModel):
    name: str = Field(min_length=1, max_length=255)
    site_id: uuid.UUID
    kind: CameraKind = CameraKind.ip
    stream_url: str | None = Field(default=None, max_length=2048)
    role: CameraRole = CameraRole.general
    resolution_w: int | None = Field(default=None, ge=1, le=15360)
    resolution_h: int | None = Field(default=None, ge=1, le=8640)
    fps: float | None = Field(default=None, gt=0, le=120)

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return strip_html(v).strip()

    @field_validator("stream_url")
    @classmethod
    def validate_rtsp(cls, v: str | None) -> str | None:
        if v is not None and not any(v.lower().startswith(s) for s in _RTSP_SCHEMES):
            raise ValueError("stream_url must use rtsp:// or rtsps:// scheme")
        return v


class CameraPatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    stream_url: str | None = Field(default=None, max_length=2048)
    role: CameraRole | None = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        return strip_html(v).strip() if v is not None else v

    @field_validator("stream_url")
    @classmethod
    def validate_rtsp(cls, v: str | None) -> str | None:
        if v is not None and not any(v.lower().startswith(s) for s in _RTSP_SCHEMES):
            raise ValueError("stream_url must use rtsp:// or rtsps:// scheme")
        return v


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


class LiveStatus(BaseModel):
    camera_id: str
    online: bool
    fps: float
    frames: int
    last_seen_s: float | None


class HealthSummary(BaseModel):
    online: int
    offline: int
    degraded: int
    unknown: int
    total: int


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


@router.get("/live-status", response_model=list[LiveStatus])
async def live_status(
    current_user: CurrentUser,
    redis: RedisClient,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[LiveStatus]:
    """Real-time camera status from Redis heartbeat keys (30 s TTL)."""
    import time as _time
    keys = await redis.keys("camera:heartbeat:*")
    result: list[LiveStatus] = []
    for key in keys:
        raw = await redis.get(key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        age = _time.time() - data.get("ts", 0)
        result.append(LiveStatus(
            camera_id=data["camera_id"],
            online=data.get("status") == "online",
            fps=data.get("fps", 0.0),
            frames=data.get("frames", 0),
            last_seen_s=round(age, 1),
        ))
    return result


@router.get("/health-summary", response_model=HealthSummary)
async def health_summary(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> HealthSummary:
    """Count cameras by health status — used by the dashboard header."""
    q = select(Camera.health_status, func.count(Camera.id)).group_by(Camera.health_status)
    if site_id:
        q = q.where(Camera.site_id == site_id)
    rows = db.execute(q).all()
    counts: dict[str, int] = {r[0].value: r[1] for r in rows}
    total = sum(counts.values())
    return HealthSummary(
        online=counts.get("online", 0),
        offline=counts.get("offline", 0),
        degraded=counts.get("degraded", 0),
        unknown=counts.get("unknown", 0),
        total=total,
    )


@router.post("/discover", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def discover_cameras(current_user: CurrentUser) -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="ONVIF discovery not implemented — Phase 2",
    )


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
