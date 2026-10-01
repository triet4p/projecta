from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.context import TrustedActorContext, TrustedRequestContext
from projecta_api.main import create_app
from projecta_api.project_workspace import catalog_revision, opaque_project_handle


class WorkspaceCore:
    async def project_catalog(
        self, context: TrustedActorContext, project_ids: list[str], limit: int = 100
    ) -> object:
        assert context.actor_id == "actor-1"
        return {
            "catalogRevision": catalog_revision(tuple(sorted(project_ids))),
            "projects": [
                {
                    "projectId": project_id,
                    "name": project_id.title(),
                    "summary": f"{project_id.title()} summary",
                    "status": "active",
                    "counts": {
                        "requirements": 1,
                        "tasks": 0,
                        "questions": 0,
                        "risks": 0,
                        "notes": 1,
                        "candidates": 0,
                    },
                    "lastActivityAt": None,
                    "health": "fresh",
                    "freshnessState": "current",
                    "freshnessRevision": "projection-1",
                }
                for project_id in project_ids[:limit]
            ],
        }

    async def request(
        self,
        context: TrustedRequestContext,
        method: str,
        path: str,
        body: object | None = None,
        key: str | None = None,
    ) -> object:
        assert context.project_id == "alpha"
        return {
            "project": {
                "projectId": "alpha",
                "name": "Alpha",
                "summary": "alpha summary",
                "status": "active",
                "counts": {
                    "requirements": 1,
                    "tasks": 0,
                    "questions": 0,
                    "risks": 0,
                    "notes": 1,
                    "candidates": 0,
                },
                "lastActivityAt": None,
                "health": "fresh",
                "freshnessState": "current",
                "freshnessRevision": "projection-1",
            },
            "currentRequirements": [{"handle": "node-h-000000000000000000000001", "label": "Requirement"}],
            "openQuestions": [],
            "tasks": [],
            "blockers": [],
            "risks": [],
            "recentNotes": [],
            "pendingCandidates": [],
            "evidenceCoverage": {"covered": 1, "total": 1},
        }

    async def readiness(self) -> bool:
        return True


async def test_catalog_and_selection_never_accept_browser_project_ids() -> None:
    settings = Settings(
        _env_file=None,
        trusted_context_secret="secret",
        runtime_mode="experience",
        experience_actor_id="actor-1",
        experience_project_catalog="beta,alpha",
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://provider.example",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="test-model",
    )
    app = create_app(settings=settings, semantic_client=WorkspaceCore())  # type: ignore[arg-type]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        catalog = await client.get("/v1/projects")
        assert catalog.status_code == 200
        assert "alpha" not in catalog.text
        assert "beta" not in catalog.text
        assert len(catalog.json()["projects"]) == 2

        handle = opaque_project_handle("alpha")
        selected = await client.post(
            "/v1/projects/selection",
            json={"handle": handle, "catalogRevision": catalog.json()["catalogRevision"]},
        )
        assert selected.status_code == 200
        assert selected.json()["project"]["handle"] == handle

        overview = await client.get(f"/v1/projects/{handle}/overview")
        assert overview.status_code == 200
        assert overview.json()["currentRequirements"][0]["label"] == "Requirement"
        forged_context = await client.get(
            f"/v1/projects/{handle}/overview",
            headers={
                "X-Projecta-Project-Id": "beta",
                "X-Projecta-Actor-Id": "attacker",
                "X-Projecta-Context-Secret": "attacker-secret",
            },
        )
        assert forged_context.status_code == 200
        assert forged_context.json()["name"] == "Alpha"
        cross_project_route = await client.get(
            f"/v1/projects/{opaque_project_handle('beta')}/overview"
        )
        assert cross_project_route.status_code == 404

        forged = await client.post(
            "/v1/projects/selection",
            json={"handle": "project-h-forged", "catalogRevision": catalog.json()["catalogRevision"]},
        )
        assert forged.status_code == 404
        assert forged.json()["code"] == "PROJECT_NOT_FOUND"

        selected_again = await client.post(
            "/v1/projects/selection",
            json={"handle": handle, "catalogRevision": catalog.json()["catalogRevision"]},
        )
        assert selected_again.status_code == 200
        settings.experience_project_catalog = "beta"
        stale = await client.get("/v1/settings/llm")
        assert stale.status_code == 409
        assert stale.json()["code"] == "PROJECT_SELECTION_STALE"
        required = await client.get("/v1/settings/llm")
        assert required.status_code == 409
        assert required.json()["code"] == "PROJECT_SELECTION_REQUIRED"
        settings.experience_project_catalog = "[]"
        empty_catalog = await client.get("/v1/projects")
        assert empty_catalog.status_code == 200
        assert empty_catalog.json()["projects"] == []
