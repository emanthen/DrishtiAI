from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_events() -> dict:
    raise NotImplementedError("events — Phase 1")


@router.get("/{event_id}")
async def get_event(event_id: str) -> dict:
    raise NotImplementedError("events — Phase 1")


@router.get("/{event_id}/snapshot")
async def get_snapshot(event_id: str) -> dict:
    raise NotImplementedError("events — Phase 1")


@router.get("/{event_id}/clip")
async def get_clip(event_id: str) -> dict:
    raise NotImplementedError("events — Phase 1")
