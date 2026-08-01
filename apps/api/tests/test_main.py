"""Smoke tests for the application composition root."""

from httpx import ASGITransport, AsyncClient

from projecta_api.main import create_app


async def test_live_health_returns_live() -> None:
    """The scaffold exposes a dependency-free liveness endpoint."""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}
