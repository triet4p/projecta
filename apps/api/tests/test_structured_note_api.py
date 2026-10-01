"""API tests for structured Note drafts, import, commit, and candidate edits."""

from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.llm.gateway import GatewayRequest, GatewayResponse
from projecta_api.main import create_app
from projecta_api.models import CaptureRequest, CaptureResponse
from projecta_api.project_workspace import catalog_revision, opaque_project_handle
from projecta_api.semantic_core import SemanticCoreProblem


class StructuredNoteCore:
    def __init__(self) -> None:
        self.captured: CaptureRequest | None = None
        self.fail_capture = False
        self.confirmed_body: object | None = None

    async def project_catalog(
        self, context: object, project_ids: list[str], limit: int = 100
    ) -> object:
        return {
            "catalogRevision": catalog_revision(tuple(project_ids)),
            "projects": [
                {
                    "projectId": project_id,
                    "name": project_id.title(),
                    "summary": "Structured Note test project",
                    "status": "active",
                    "counts": {
                        "requirements": 0,
                        "tasks": 0,
                        "questions": 0,
                        "risks": 0,
                        "notes": 0,
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

    async def capture(
        self, context: TrustedRequestContext, key: str, request: CaptureRequest
    ) -> CaptureResponse:
        if self.fail_capture:
            raise SemanticCoreProblem(422, "CANDIDATE_INVALID", "semantic validation failed")
        self.captured = request
        return CaptureResponse.model_validate(
            {
                "requestId": context.request_id,
                "note": {"id": "note-01", "recordedAt": datetime(2026, 8, 10, tzinfo=UTC)},
                "candidates": [],
            }
        )

    async def request(
        self,
        context: TrustedRequestContext,
        method: str,
        path: str,
        body: object | None = None,
        key: str | None = None,
    ) -> object:
        if path.endswith("/source-context"):
            raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "not a manual candidate")
        if path.endswith("/validations"):
            return {
                "requestId": context.request_id,
                "candidateId": "candidate-internal",
                "conforms": True,
                "violations": [],
                "validatedAt": "2026-08-10T00:00:00Z",
            }
        if path.endswith("/confirmations"):
            self.confirmed_body = body
            return {
                "requestId": context.request_id,
                "candidateId": "candidate-internal",
                "decision": "confirmed",
                "assertedItemId": "requirement-internal",
            }
        if path.startswith("/v1/projects/alpha/notes"):
            if path.endswith("/notes/note-h-abcdef12"):
                return {
                    "noteHandle": "note-h-abcdef12",
                    "title": "URL source",
                    "rawText": "Visit https://example.test/a",
                    "author": "actor-1",
                    "recordedAt": "2026-08-10T00:00:00Z",
                    "items": [
                        {
                            "itemType": "research-need",
                            "content": "Visit https://example.test/a",
                            "startOffset": 0,
                            "endOffset": 28,
                        }
                    ],
                    "evidenceCoverage": 1.0,
                    "candidateState": "source-only",
                }
            return {"notes": [], "hasMore": False}
        return {}

    async def entity_link_context(
        self, context: TrustedRequestContext, limit: int = 50
    ) -> list[dict[str, str]]:
        return [{"id": "Requirement--existing", "type": "Requirement", "label": "Existing"}]

    async def readiness(self) -> bool:
        return True


def _settings() -> Settings:
    return Settings(
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


async def _selected_client(core: StructuredNoteCore) -> tuple[AsyncClient, str]:
    app = create_app(
        settings=_settings(), semantic_client=core, gateway=StructuredNoteGateway()
    )  # type: ignore[arg-type]
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    catalog = await client.get("/v1/projects")
    handle = opaque_project_handle("alpha")
    selected = await client.post(
        "/v1/projects/selection",
        json={"handle": handle, "catalogRevision": catalog.json()["catalogRevision"]},
    )
    assert selected.status_code == 200
    return client, handle


class StructuredNoteGateway:
    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        if "<UNTRUSTED_NOTE>\n\n\n</UNTRUSTED_NOTE>" in request.user_prompt:
            extraction = ExtractionResponse.model_validate(
                {
                    "schemaVersion": "m3.v1",
                    "modelId": "test-model",
                    "modelVersion": "test-model-v1",
                    "entities": [],
                    "relations": [],
                    "links": [],
                    "abstentionReason": "No supported proposal is present",
                }
            )
        else:
            extraction = ExtractionResponse.model_validate(
                {
                    "schemaVersion": "m3.v1",
                    "modelId": "test-model",
                    "modelVersion": "test-model-v1",
                    "entities": [
                        {
                            "type": "Task",
                            "label": "Confirm address",
                            "evidence": {
                                "startOffset": 0,
                                "endOffset": 16,
                                "text": "Confirm address.",
                            },
                            "confidence": 0.9,
                        },
                        {
                            "type": "Question",
                            "label": "Blocked question",
                            "evidence": {
                                "startOffset": 17,
                                "endOffset": 33,
                                "text": "What is blocked?",
                            },
                            "confidence": 0.9,
                        },
                    ],
                    "relations": [],
                    "links": [],
                    "abstentionReason": None,
                }
            )
        return GatewayResponse(extraction=extraction)


async def test_draft_create_replay_and_optimistic_update() -> None:
    core = StructuredNoteCore()
    client, handle = await _selected_client(core)
    try:
        body = {
            "title": "Checkout",
            "items": [{"itemType": "task", "content": "Review address."}],
        }
        created = await client.post(
            f"/v1/projects/{handle}/notes/drafts",
            headers={"Idempotency-Key": "draft-1"},
            json=body,
        )
        assert created.status_code == 201
        assert created.json()["rawText"] == "Review address."
        assert created.json()["items"][0]["startOffset"] == 0
        replay = await client.post(
            f"/v1/projects/{handle}/notes/drafts",
            headers={"Idempotency-Key": "draft-1"},
            json=body,
        )
        assert replay.status_code == 200
        assert replay.json()["draftHandle"] == created.json()["draftHandle"]
        updated = await client.put(
            f"/v1/projects/{handle}/notes/drafts/{created.json()['draftHandle']}",
            headers={"If-Match": "1"},
            json={"title": "Checkout", "items": []},
        )
        assert updated.status_code == 200
        assert updated.json()["revision"] == 2
        stale = await client.put(
            f"/v1/projects/{handle}/notes/drafts/{created.json()['draftHandle']}",
            headers={"If-Match": "1"},
            json=body,
        )
        assert stale.status_code == 409
    finally:
        await client.aclose()


async def test_commit_derives_title_and_segments_and_empty_draft_fails() -> None:
    core = StructuredNoteCore()
    client, handle = await _selected_client(core)
    try:
        created = await client.post(
            f"/v1/projects/{handle}/notes/drafts",
            headers={"Idempotency-Key": "draft-commit"},
            json={
                "title": "Unicode note",
                "items": [
                    {"itemType": "question", "content": "Café 🚀?"},
                    {"itemType": "risk", "content": "Timeout."},
                ],
            },
        )
        committed = await client.post(
            f"/v1/projects/{handle}/notes/drafts/{created.json()['draftHandle']}/commit",
            headers={"Idempotency-Key": "commit-1"},
        )
        assert committed.status_code == 201
        assert committed.json()["draftStatus"] == "committed"
        assert core.captured is not None
        assert core.captured.title == "Unicode note"
        assert core.captured.raw_text == "Café 🚀?\nTimeout."
        assert core.captured.segments[1].start_offset == len("Café 🚀?") + 1

        empty = await client.post(
            f"/v1/projects/{handle}/notes/drafts",
            headers={"Idempotency-Key": "draft-empty"},
            json={"title": "Empty", "items": []},
        )
        rejected = await client.post(
            f"/v1/projects/{handle}/notes/drafts/{empty.json()['draftHandle']}/commit",
            headers={"Idempotency-Key": "commit-empty"},
        )
        assert rejected.status_code == 422
    finally:
        await client.aclose()


async def test_idempotency_conflict_and_semantic_failure_leave_draft_uncommitted() -> None:
    core = StructuredNoteCore()
    client, handle = await _selected_client(core)
    try:
        first = await client.post(
            f"/v1/projects/{handle}/notes/drafts",
            headers={"Idempotency-Key": "same-key"},
            json={"title": "One", "items": [{"itemType": "task", "content": "A"}]},
        )
        conflict = await client.post(
            f"/v1/projects/{handle}/notes/drafts",
            headers={"Idempotency-Key": "same-key"},
            json={"title": "Different", "items": [{"itemType": "task", "content": "A"}]},
        )
        assert conflict.status_code == 409

        core.fail_capture = True
        failed_commit = await client.post(
            f"/v1/projects/{handle}/notes/drafts/{first.json()['draftHandle']}/commit",
            headers={"Idempotency-Key": "failed-commit"},
        )
        assert failed_commit.status_code == 422
        still_draft = await client.get(
            f"/v1/projects/{handle}/notes/drafts/{first.json()['draftHandle']}"
        )
        assert still_draft.status_code == 200
        assert still_draft.json().get("committedNoteHandle") is None
        assert still_draft.json()["draftStatus"] == "draft"
    finally:
        await client.aclose()


async def test_import_abstains_without_persisting_and_candidate_edits_are_audited() -> None:
    core = StructuredNoteCore()
    client, handle = await _selected_client(core)
    try:
        abstained = await client.post(
            f"/v1/projects/{handle}/notes/import", json={"rawText": "\r\n"}
        )
        assert abstained.status_code == 200
        assert abstained.json()["status"] == "abstained"
        proposed = await client.post(
            f"/v1/projects/{handle}/notes/import",
            json={"rawText": "Confirm address.\nWhat is blocked?"},
        )
        assert proposed.json()["status"] == "proposed"
        assert [item["itemType"] for item in proposed.json()["proposals"]] == ["task", "question"]
        edited = await client.post(
            f"/v1/projects/{handle}/candidates/candidate-h-abcdef12/edits",
            json={"label": "Corrected label", "expectedRevision": 1},
        )
        assert edited.status_code == 200
        assert edited.json()["revision"] == 1
        options = await client.get(f"/v1/projects/{handle}/candidate-edit-options")
        assert options.status_code == 200
        assert options.json()["entityLinks"][0]["label"] == "Existing"
        assert options.json()["assignments"][0]["label"] == "Current reviewer"
        validated = await client.post(
            f"/v1/projects/{handle}/candidates/candidate-h-abcdef12/validations"
        )
        assert validated.status_code == 200
        assert validated.json()["correctionRevision"] == 1
        assert validated.json()["correctionsValidated"] is True
        assert validated.json()["corrections"]["label"] == "Corrected label"
        confirmed = await client.post(
            f"/v1/projects/{handle}/candidates/candidate-h-abcdef12/confirmations",
            headers={"Idempotency-Key": "confirm-corrected"},
            json={
                "assertion": {
                    "type": "Requirement",
                    "label": "Stale browser label",
                    "validFrom": "2026-08-10",
                },
                "correctionRevision": 1,
            },
        )
        assert confirmed.status_code == 200
        assert core.confirmed_body == {
            "assertion": {
                "type": "Requirement",
                "label": "Corrected label",
                "validFrom": "2026-08-10",
            }
        }
        stale_confirmation = await client.post(
            f"/v1/projects/{handle}/candidates/candidate-h-abcdef12/confirmations",
            headers={"Idempotency-Key": "confirm-stale"},
            json={
                "assertion": {
                    "type": "Requirement",
                    "label": "Corrected label",
                    "validFrom": "2026-08-10",
                },
                "correctionRevision": 0,
            },
        )
        assert stale_confirmation.status_code == 409
        stale = await client.post(
            f"/v1/projects/{handle}/candidates/candidate-h-abcdef12/edits",
            json={"label": "Again", "expectedRevision": 1},
        )
        assert stale.status_code == 409
        detail = await client.get(f"/v1/projects/{handle}/notes/note-h-abcdef12")
        assert detail.status_code == 200
        assert detail.json()["rawText"] == "Visit https://example.test/a"
    finally:
        await client.aclose()
