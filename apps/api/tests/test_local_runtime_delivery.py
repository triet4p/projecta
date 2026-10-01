from pathlib import Path

from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.main import create_app


class ReadySemanticCore:
    async def readiness(self) -> bool:
        return True


def _settings(assets: Path) -> Settings:
    return Settings(
        _env_file=None,
        runtime_mode="experience",
        trusted_context_secret="local-test-context",
        secret_store_master_key=Fernet.generate_key().decode("ascii"),
        experience_actor_id="local-operator",
        experience_project_catalog="projecta-local",
        web_assets_directory=assets,
    )


async def test_api_serves_spa_and_static_assets_without_shadowing_api_routes(tmp_path: Path) -> None:
    assets = tmp_path / "web"
    (assets / "assets").mkdir(parents=True)
    (assets / "index.html").write_text("<main>Projecta package UI</main>", encoding="utf-8")
    (assets / "assets" / "app.js").write_text("window.projecta = true;", encoding="utf-8")
    app = create_app(settings=_settings(assets), semantic_client=ReadySemanticCore())  # type: ignore[arg-type]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        index = await client.get("/")
        client_route = await client.get("/notes")
        asset = await client.get("/assets/app.js")
        missing_asset = await client.get("/assets/missing.js")
        api_miss = await client.get("/v1/not-a-route")
        health = await client.get("/health/live")

    assert index.status_code == 200 and "Projecta package UI" in index.text
    assert client_route.status_code == 200 and "Projecta package UI" in client_route.text
    assert asset.status_code == 200 and "window.projecta = true" in asset.text
    assert missing_asset.status_code == 404
    assert api_miss.status_code == 404 and "Projecta package UI" not in api_miss.text
    assert health.status_code == 200 and health.json() == {"status": "live"}


async def test_invalid_packaged_web_directory_fails_readiness(tmp_path: Path) -> None:
    app = create_app(
        settings=_settings(tmp_path / "missing-web"),
        semantic_client=ReadySemanticCore(),
    )  # type: ignore[arg-type]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        readiness = await client.get("/health/ready")

    assert readiness.status_code == 503
    assert readiness.json()["reasonCode"] == "CONFIGURATION_INVALID"
    assert "WEB_ASSETS_CONFIGURATION_INVALID" in readiness.json()["problems"]
