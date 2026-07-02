"""Auth endpoint unit tests — uses ASGI transport, no real DB."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from drishtiai_api.main import app


@pytest.mark.asyncio
async def test_login_wrong_password() -> None:
    """Wrong password returns 401."""
    mock_user = None
    with (
        patch("drishtiai_api.routers.auth.get_db") as mock_get_db,
    ):
        db = MagicMock()
        db.scalar.return_value = mock_user
        mock_get_db.return_value = iter([db])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/auth/login",
                json={"email": "nobody@example.com", "password": "wrong"},
            )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth() -> None:
    """GET /auth/me without a token returns 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_no_auth_needed() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
