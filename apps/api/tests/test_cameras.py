"""Camera endpoint unit tests."""
import pytest
from httpx import AsyncClient, ASGITransport

from drishtiai_api.main import app


@pytest.mark.asyncio
async def test_cameras_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/cameras")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_add_camera_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/cameras",
            json={"name": "Test", "site_id": "00000000-0000-0000-0000-000000000001"},
        )
    assert response.status_code == 403
