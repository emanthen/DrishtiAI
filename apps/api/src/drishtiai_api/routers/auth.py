from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login() -> dict:
    # Phase 1: implement JWT auth backed by Django user store
    raise NotImplementedError("auth not implemented yet — Phase 1")


@router.post("/refresh")
async def refresh() -> dict:
    raise NotImplementedError("auth not implemented yet — Phase 1")


@router.post("/logout")
async def logout() -> dict:
    raise NotImplementedError("auth not implemented yet — Phase 1")
