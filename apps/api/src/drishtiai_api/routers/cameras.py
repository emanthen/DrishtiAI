from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_cameras() -> dict:
    raise NotImplementedError("cameras — Phase 1")


@router.post("")
async def add_camera() -> dict:
    raise NotImplementedError("cameras — Phase 1")


@router.post("/discover")
async def discover_cameras() -> dict:
    raise NotImplementedError("ONVIF discovery — Phase 2")
