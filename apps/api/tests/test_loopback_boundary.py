from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from projecta_api.loopback_boundary import (
    LoopbackBoundaryMiddleware,
    host_header_allowed,
    origin_header_allowed,
)

pytestmark = pytest.mark.local_contract

_PORT = 18732


def _client(app: FastAPI, port: int = _PORT) -> TestClient:
    return TestClient(LoopbackBoundaryMiddleware(app, port), base_url=f"http://127.0.0.1:{port}")


@pytest.fixture(name="app")
def app_fixture() -> FastAPI:
    app = FastAPI()

    @app.api_route("/probe", methods=["GET", "POST"])
    async def probe() -> dict[str, str]:
        return {"status": "served"}

    return app


def test_loopback_host_names_are_allowed() -> None:
    for host in (
        f"127.0.0.1:{_PORT}",
        "127.0.0.1",
        f"localhost:{_PORT}",
        "localhost",
        f"[::1]:{_PORT}",
        "LOCALHOST:18732",
    ):
        assert host_header_allowed(host), host


def test_foreign_or_missing_host_is_refused() -> None:
    for host in (None, "", "evil.example.com", f"evil.example.com:{_PORT}", "projecta-bootstrap.localhost"):
        assert not host_header_allowed(host), host


def test_absent_or_loopback_origin_is_allowed() -> None:
    assert origin_header_allowed(None, _PORT)
    assert origin_header_allowed(f"http://127.0.0.1:{_PORT}", _PORT)
    assert origin_header_allowed(f"http://localhost:{_PORT}", _PORT)


def test_foreign_origin_is_refused() -> None:
    for origin in (
        "https://evil.example.com",
        f"http://evil.example.com:{_PORT}",
        f"http://127.0.0.1:{_PORT + 1}",
        "http://user:pass@127.0.0.1:18732",
        "null",
        "not-a-url",
    ):
        assert not origin_header_allowed(origin, _PORT), origin


def test_loopback_request_reaches_the_application(app: FastAPI) -> None:
    client = _client(app)
    response = client.get("/probe")
    assert response.status_code == 200
    assert response.json() == {"status": "served"}


def test_foreign_host_request_is_refused(app: FastAPI) -> None:
    client = TestClient(LoopbackBoundaryMiddleware(app, _PORT), base_url="http://testserver")
    response = client.get("/probe")
    assert response.status_code == 403
    assert response.json()["code"] == "LOOPBACK_BOUNDARY_REJECTED"


def test_foreign_origin_request_is_refused(app: FastAPI) -> None:
    client = _client(app)
    response = client.post("/probe", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 403
    assert response.json()["code"] == "LOOPBACK_BOUNDARY_REJECTED"


def test_same_origin_loopback_post_reaches_the_application(app: FastAPI) -> None:
    client = _client(app)
    response = client.post("/probe", headers={"Origin": f"http://127.0.0.1:{_PORT}"})
    assert response.status_code == 200
