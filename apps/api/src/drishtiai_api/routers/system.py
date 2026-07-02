from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SystemHealth(BaseModel):
    api: str
    database: str
    redis: str
    minio: str
    pipeline: str


@router.get("/health", response_model=SystemHealth)
async def system_health() -> SystemHealth:
    # Phase 10: add real probes for each subsystem
    return SystemHealth(
        api="ok",
        database="unknown",
        redis="unknown",
        minio="unknown",
        pipeline="unknown",
    )
