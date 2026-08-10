import pytest
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.context import TrustedActorContext, TrustedRequestContext
from projecta_api.graph_projection import project_graph_page, project_node_detail
from projecta_api.main import create_app
from projecta_api.project_workspace import catalog_revision, opaque_project_handle


class GraphCore:
    async def project_catalog(
        self, context: TrustedActorContext, project_ids: list[str], limit: int = 100
    ) -> object:
        return {
            "catalogRevision": catalog_revision(tuple(project_ids)),
            "projects": [
                {
                    "projectId": project_ids[0],
                    "name": "Alpha",
                    "status": "active",
                    "counts": {
                        "requirements": 1,
                        "tasks": 0,
                        "questions": 0,
                        "risks": 0,
                        "notes": 1,
                        "candidates": 1,
                    },
                    "health": "fresh",
                    "freshnessState": "current",
                    "freshnessRevision": "projection-r1",
                }
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
        if "/graph/nodes/" in path:
            return {
                "_projecta_http_status": 200,
                "handle": "node-h-1234567890abcdef",
                "label": "Tax API timeout is 15%",
                "semanticType": "Risk",
                "lifecycleState": "current",
                "verificationState": "asserted",
                "provenanceState": "source-backed",
                "evidenceCount": 1,
                "projectScope": "selected",
                "dates": {},
                "availableActions": ["view-detail", "view-evidence"],
                "projectLabel": "Alpha",
                "freshness": "available",
                "relations": [],
                "evidence": [],
                "lifecycle": [],
            }
        if path.endswith("/candidates?status=pending-review&limit=50"):
            return {
                "sourceRevision": "source-r1",
                "stale": False,
                "candidates": [
                    {
                        "handle": "candidate-h-abcdef1234567890",
                        "label": "Address confirmation",
                        "sourceExcerpt": "Confirm the address.",
                        "proposedType": "Requirement",
                        "proposedRelations": [],
                        "validationState": "pending",
                        "lifecycleState": "pending-review",
                        "confidence": 0.9,
                        "evidenceCount": 1,
                    }
                ],
                "hasMore": False,
            }
        return {
            "projectionVersion": "s8.graph.v1",
            "sourceRevision": "source-r1",
            "materializationRevision": "materialized-r1",
            "asOf": "2026-08-10T10:00:00Z",
            "stale": False,
            "partial": False,
            "nodes": [
                {
                    "handle": "node-h-abcdef1234567890",
                    "label": "Address confirmation",
                    "semanticType": "Requirement",
                    "lifecycleState": "current",
                    "verificationState": "asserted",
                    "provenanceState": "source-backed",
                    "evidenceCount": 1,
                    "projectScope": "selected",
                    "dates": {},
                    "availableActions": ["view-detail", "view-evidence"],
                }
            ],
            "edges": [],
            "page": {
                "nodeLimit": 50,
                "edgeLimit": 100,
                "hasMore": False,
                "continuation": None,
                "expansionAvailable": True,
            },
            "filters": {
                "semanticTypes": [],
                "verificationStates": [],
                "lifecycleStates": [],
                "provenanceStates": [],
                "relationTypes": [],
                "evidence": "any",
            },
        }

    async def readiness(self) -> bool:
        return True


async def _selected_client() -> AsyncClient:
    settings = Settings(
        _env_file=None,
        trusted_context_secret="secret",
        runtime_mode="experience",
        experience_actor_id="actor-1",
        experience_project_catalog="alpha",
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://provider.example",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="test-model",
    )
    app = create_app(settings=settings, semantic_client=GraphCore())  # type: ignore[arg-type]
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    catalog = await client.get("/v1/projects")
    await client.post(
        "/v1/projects/selection",
        json={
            "handle": opaque_project_handle("alpha"),
            "catalogRevision": catalog.json()["catalogRevision"],
        },
    )
    return client


async def test_graph_projection_is_finite_and_id_free() -> None:
    client = await _selected_client()
    try:
        handle = opaque_project_handle("alpha")
        response = await client.get(f"/v1/projects/{handle}/graph?nodeLimit=50&edgeLimit=100")
        assert response.status_code == 200
        body = response.json()
        assert body["projectionVersion"] == "s8.graph.v1"
        assert body["nodes"][0]["label"] == "Address confirmation"
        assert body["nodes"][0]["handle"].startswith("node-h-")
        assert "https://" not in response.text

        detail = await client.get(f"/v1/projects/{handle}/graph/nodes/node-h-abcdef1234567890")
        assert detail.status_code == 200
        assert detail.json()["projectHandle"] == handle
    finally:
        await client.aclose()


async def test_graph_rejects_unknown_filters_and_raw_handles() -> None:
    client = await _selected_client()
    try:
        handle = opaque_project_handle("alpha")
        unknown = await client.get(f"/v1/projects/{handle}/graph?semanticTypes=UnreleasedType")
        assert unknown.status_code == 400
        raw = await client.get(f"/v1/projects/{handle}/graph/nodes/https://internal/resource")
        assert raw.status_code in {400, 404}
    finally:
        await client.aclose()


def test_graph_projection_keeps_cycles_bounded_and_repeatable() -> None:
    payload = {
        "projectionVersion": "s8.graph.v1",
        "sourceRevision": "source-r1",
        "materializationRevision": "materialized-r1",
        "asOf": "2026-08-10T10:00:00Z",
        "stale": False,
        "partial": False,
        "nodes": [
            {
                "handle": "node-h-abcdef1234567890",
                "label": "Cycle A",
                "semanticType": "Requirement",
                "lifecycleState": "current",
                "verificationState": "asserted",
                "provenanceState": "source-backed",
                "evidenceCount": 0,
                "projectScope": "selected",
                "dates": {},
                "availableActions": [],
            }
        ],
        "edges": [
            {
                "handle": "edge-h-abcdef1234567890",
                "sourceHandle": "node-h-abcdef1234567890",
                "targetHandle": "node-h-abcdef1234567890",
                "relationType": "supports",
                "direction": "source-to-target",
                "verificationState": "asserted",
                "provenanceState": "source-backed",
                "evidenceCount": 0,
            }
        ],
        "page": {"nodeLimit": 1, "edgeLimit": 1, "hasMore": False, "expansionAvailable": True},
        "filters": {
            "semanticTypes": [],
            "verificationStates": [],
            "lifecycleStates": [],
            "provenanceStates": [],
            "relationTypes": [],
            "evidence": "any",
        },
    }
    first = project_graph_page(payload, "req-1", "project-h-abcdef1234567890", 1, 1)
    second = project_graph_page(payload, "req-1", "project-h-abcdef1234567890", 1, 1)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert len(first.nodes) == len(first.edges) == 1


def test_node_detail_drops_private_transport_status() -> None:
    detail = project_node_detail(
        {
            "_projecta_http_status": 200,
            "handle": "node-h-1234567890abcdef",
            "label": "Meeting 10/08",
            "semanticType": "Note",
            "lifecycleState": "current",
            "verificationState": "unverified",
            "provenanceState": "source-backed",
            "evidenceCount": 0,
            "projectScope": "selected",
            "dates": {},
            "availableActions": ["view-detail"],
            "projectLabel": "Alpha",
            "freshness": "available",
            "relations": [],
            "evidence": [],
            "lifecycle": [],
        },
        "experience-request",
        "project-h-abcdef1234567890",
    )

    assert detail.semantic_type == "Note"
    assert detail.request_id == "experience-request"
    assert "_projecta_http_status" not in detail.model_dump(mode="json", by_alias=True)


def test_graph_projection_fails_when_semantic_state_is_missing() -> None:
    payload = {
        "projectionVersion": "s8.graph.v1",
        "sourceRevision": "source-r1",
        "materializationRevision": "materialized-r1",
        "asOf": "2026-08-10T10:00:00Z",
        "stale": False,
        "partial": False,
        "nodes": [
            {
                "handle": "node-h-abcdef1234567890",
                "label": "Missing truth state",
                "semanticType": "Requirement",
                "lifecycleState": "current",
                "provenanceState": "source-backed",
                "evidenceCount": 0,
                "projectScope": "selected",
                "dates": {},
                "availableActions": [],
            }
        ],
        "edges": [],
        "page": {
            "nodeLimit": 1,
            "edgeLimit": 1,
            "hasMore": False,
            "continuation": None,
            "expansionAvailable": False,
        },
        "filters": {
            "semanticTypes": [],
            "verificationStates": [],
            "lifecycleStates": [],
            "provenanceStates": [],
            "relationTypes": [],
            "evidence": "any",
        },
    }
    with pytest.raises(ValueError, match="verificationState"):
        project_graph_page(payload, "req-1", "project-h-abcdef1234567890", 1, 1)
