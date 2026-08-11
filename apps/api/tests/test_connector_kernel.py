"""Focused D-task tests for the bounded connector kernel."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from projecta_api.connectors.authorization import (
    ConnectorPolicy,
    DeterministicTestPrincipalAdapter,
)
from projecta_api.connectors.contracts import (
    PullEventsCommand,
    RawEventCandidate,
    SyncCommand,
    sha256_digest,
)
from projecta_api.connectors.event_validation import (
    CanonicalEventValidationError,
    canonical_body_bytes,
    validate_and_canonicalize,
)
from projecta_api.connectors.installation_service import (
    ConnectorInstallationService,
    InstallationMutation,
)
from projecta_api.connectors.json_mock import JsonMockAdapter, JsonMockFixture
from projecta_api.connectors.orchestration import ConnectorSyncOrchestrator
from projecta_api.connectors.registry import ConnectorRegistry, ConnectorRegistryError
from projecta_api.connectors.telemetry import InMemoryConnectorTelemetry
from projecta_api.context import TrustedActorContext
from projecta_api.evidence.ports import EvidencePutRequest, EvidenceReceipt
from projecta_api.operational.ports import EventClaim, InstallationRecord, SyncRunRecord

NOW = datetime.now(UTC).replace(microsecond=0)


def fixture() -> JsonMockFixture:
    return JsonMockFixture.model_validate(
        {
            "fixtureVersion": "json-mock.v1",
            "connectorType": "json-mock",
            "resources": [
                {
                    "externalReference": "fixture://project-a/message-001",
                    "occurredAt": NOW.isoformat(),
                    "eventType": "source.created",
                    "actorHint": "fixture-user-001",
                    "contentType": "application/json",
                    "content": {
                        "title": "Import me",
                        "items": [{"type": "question", "text": "Review"}],
                    },
                }
            ],
        }
    )


def test_registry_is_explicit_finite_and_duplicate_safe() -> None:
    registry = ConnectorRegistry()
    adapter = JsonMockAdapter(fixture())
    registry.register(adapter)
    assert registry.catalog()[0].connector_type == "json-mock"
    assert "inbound-import" in registry.capabilities("json-mock")
    with pytest.raises(ConnectorRegistryError, match="ADAPTER_DUPLICATE_REGISTRATION"):
        registry.register(adapter)
    with pytest.raises(ConnectorRegistryError, match="ADAPTER_UNKNOWN_TYPE"):
        registry.resolve("future-provider")


@pytest.mark.asyncio
async def test_json_mock_is_bounded_deterministic_and_has_no_semantic_side_effect() -> None:
    adapter = JsonMockAdapter(fixture())
    command = {
        "installationId": "install-a",
        "projectId": "project-a",
        "fixtureReference": "fixture://project-a",
        "max_events": 100,
        "max_bytes": 10 * 1024 * 1024,
        "deadline": NOW + timedelta(minutes=1),
        "correlationId": "req-a",
        "operationId": "op-a",
        "capability": "inbound-import",
    }
    result = await adapter.pull_events(PullEventsCommand.model_validate(command))
    assert result.outcome == "succeeded"
    assert result.events[0].event_id == "evt-001"
    assert result.next_cursor is not None and result.next_cursor.value == "1"
    assert adapter.pull_call_count == 1


@pytest.mark.asyncio
async def test_json_mock_pull_is_scoped_to_the_exact_installation_fixture() -> None:
    scoped_fixture = JsonMockFixture.model_validate(
        {
            "fixtureVersion": "json-mock.v1",
            "connectorType": "json-mock",
            "resources": [
                {
                    "externalReference": f"fixture://project-{suffix}/message-001",
                    "occurredAt": NOW.isoformat(),
                    "eventType": "source.created",
                    "contentType": "application/json",
                    "content": {"title": suffix, "items": [{"type": "task", "text": suffix}]},
                }
                for suffix in ("a", "ab", "b")
            ],
        }
    )
    adapter = JsonMockAdapter(scoped_fixture)
    result = await adapter.pull_events(
        PullEventsCommand(
            installationId="install-a",
            projectId="project-a",
            fixtureReference="fixture://project-a",
            deadline=NOW + timedelta(minutes=1),
            correlationId="req-scope",
            operationId="op-scope",
            capability="inbound-import",
        )
    )

    assert len(result.events) == 1
    assert result.events[0].external_reference == "fixture://project-a/message-001"


def test_canonical_event_binds_server_scope_and_recomputes_hashes() -> None:
    content = b'{"title":"Import me"}'
    candidate = RawEventCandidate(
        eventId="evt-001",
        eventType="source.created",
        externalReference="fixture://project-a/message-001",
        occurredAt=NOW,
        contentType="application/json",
        contentBytes=content,
    )
    event = validate_and_canonicalize(
        candidate,
        project_id="project-a",
        installation_id="install-a",
        connector_type="json-mock",
        evidence_reference="ev_" + "a" * 22,
        now=NOW,
    )
    assert event.project_scope == "project-a"
    assert event.installation_scope == "install-a"
    assert event.content.content_hash == sha256_digest(content)
    assert event.canonical_body_hash.startswith("sha256:")
    relocated = validate_and_canonicalize(
        candidate,
        project_id="project-a",
        installation_id="install-a",
        connector_type="json-mock",
        evidence_reference="ev_" + "b" * 22,
        now=NOW,
    )
    assert relocated.canonical_body_hash == event.canonical_body_hash
    assert canonical_body_bytes(relocated) == canonical_body_bytes(event)
    assert b"contentRef" not in canonical_body_bytes(event)


def test_canonical_event_rejects_scope_path_timestamp_and_duplicate_json() -> None:
    base = {
        "eventId": "evt-001",
        "eventType": "source.created",
        "externalReference": "fixture://project-a/message-001",
        "occurredAt": NOW,
        "contentType": "application/json",
        "contentBytes": b'{"a":1,"a":2}',
    }
    with pytest.raises(CanonicalEventValidationError, match="EVENT_CONTENT_INVALID"):
        validate_and_canonicalize(
            RawEventCandidate.model_validate(base),
            project_id="project-a",
            installation_id="install-a",
            connector_type="json-mock",
            evidence_reference="ev_" + "a" * 22,
            now=NOW,
        )
    base["externalReference"] = "../secrets"
    base["contentBytes"] = b"{}"
    with pytest.raises(CanonicalEventValidationError, match="EVENT_REFERENCE_INVALID"):
        validate_and_canonicalize(
            RawEventCandidate.model_validate(base),
            project_id="project-a",
            installation_id="install-a",
            connector_type="json-mock",
            evidence_reference="ev_" + "a" * 22,
            now=NOW,
        )
    base["externalReference"] = "fixture://project-a/message-001"
    base["contentBytes"] = b'{"value":NaN}'
    with pytest.raises(CanonicalEventValidationError, match="EVENT_CONTENT_INVALID"):
        validate_and_canonicalize(
            RawEventCandidate.model_validate(base),
            project_id="project-a",
            installation_id="install-a",
            connector_type="json-mock",
            evidence_reference="ev_" + "a" * 22,
            now=NOW,
        )


class InMemoryRepository:
    def __init__(self) -> None:
        self.installation = InstallationRecord(
            "install-a",
            "project-a",
            "json-mock",
            {"capabilities": ["inbound-import"], "fixtureReference": "fixture://project-a"},
            None,
            True,
            1,
            NOW,
            NOW,
        )
        self.events: dict[str, tuple[str, str | None]] = {}
        self.cursor_value: str | None = None
        self.cursor_revision = 0
        self.runs: dict[str, SyncRunRecord] = {}
        self.keys: dict[str, str] = {}
        self.dead_letters = 0
        self.dead_letter_failure = False
        self.audit_events: list[dict[str, object]] = []

    def get_installation(self, project_id: str, installation_id: str) -> InstallationRecord | None:
        return (
            self.installation
            if (project_id, installation_id)
            == (self.installation.project_id, self.installation.installation_id)
            else None
        )

    def get_cursor(self, project_id: str, installation_id: str):
        if self.cursor_revision == 0:
            return None
        from projecta_api.operational.ports import CursorRecord

        return CursorRecord(
            installation_id, project_id, self.cursor_value, self.cursor_revision, NOW
        )

    def start_run(
        self,
        *,
        project_id: str,
        installation_id: str,
        run_id: str,
        idempotency_key: str,
        retry_of_run_id: str | None = None,
    ) -> SyncRunRecord:
        if idempotency_key in self.keys:
            return self.runs[self.keys[idempotency_key]]
        run = SyncRunRecord(
            run_id,
            installation_id,
            project_id,
            "running",
            NOW,
            None,
            None,
            1,
            retry_of_run_id,
            None,
            None,
        )
        self.runs[run_id] = run
        self.keys[idempotency_key] = run_id
        return run

    def get_run(self, project_id: str, installation_id: str, run_id: str) -> SyncRunRecord | None:
        return self.runs.get(run_id)

    def upsert_installation(
        self,
        *,
        project_id: str,
        installation_id: str,
        connector_type: str,
        capability_snapshot: dict[str, object],
        secret_reference: str | None,
        enabled: bool,
        expected_revision: int | None,
        audit_operation: str | None = None,
        actor_reference: str | None = None,
        correlation_id: str | None = None,
    ) -> InstallationRecord:
        if expected_revision is not None and self.installation.revision != expected_revision:
            from projecta_api.operational.errors import RevisionConflict

            raise RevisionConflict("stale")
        revision = self.installation.revision + 1 if expected_revision is not None else 1
        self.installation = InstallationRecord(
            installation_id,
            project_id,
            connector_type,
            capability_snapshot,
            secret_reference,
            enabled,
            revision,
            NOW,
            NOW,
        )
        if audit_operation is not None:
            self.audit_events.append(
                {
                    "project_id": project_id,
                    "installation_id": installation_id,
                    "operation": audit_operation,
                    "outcome": "accepted",
                    "actor_reference": actor_reference,
                    "correlation_id": correlation_id,
                    "revision": revision,
                }
            )
        return self.installation

    def finish_run(
        self,
        *,
        project_id: str,
        installation_id: str,
        run_id: str,
        outcome: str,
        failure_code: str | None = None,
        failure_detail: str | None = None,
        event_count: int = 0,
        replay_count: int = 0,
        dead_letter_id: int | None = None,
    ) -> SyncRunRecord:
        old = self.runs[run_id]
        if old.terminal_at is not None:
            return old
        updated = SyncRunRecord(
            old.run_id,
            old.installation_id,
            old.project_id,
            outcome,
            old.started_at,
            NOW,
            outcome,
            old.revision + 1,
            old.retry_of_run_id,
            failure_code,
            failure_detail,
            event_count,
            replay_count,
            dead_letter_id,
        )
        self.runs[run_id] = updated
        return updated

    def claim_event(
        self,
        *,
        project_id: str,
        installation_id: str,
        event_id: str,
        body_hash: str,
        content_reference: str,
    ) -> EventClaim:
        old = self.events.get(event_id)
        if old is None:
            self.events[event_id] = (body_hash, None)
            return EventClaim(event_id, project_id, installation_id, "new", None, content_reference)
        if old[0] != body_hash:
            from projecta_api.operational.errors import IdempotencyConflict

            raise IdempotencyConflict("conflict")
        return EventClaim(
            event_id,
            project_id,
            installation_id,
            "replayed"
            if old[1] in {"accepted", "replayed"}
            else ("new" if old[1] in {"failed", "cancelled"} else "in_progress"),
            old[1],
            content_reference,
        )

    def complete_event(
        self,
        *,
        project_id: str,
        installation_id: str,
        event_id: str,
        body_hash: str,
        outcome: str,
        checkpoint: str | None,
        expected_cursor_revision: int | None,
    ):
        old = self.events[event_id]
        if old[1] in {"accepted", "replayed"}:
            return self.get_cursor(project_id, installation_id)
        self.events[event_id] = (old[0], outcome)
        if outcome == "accepted" and checkpoint is not None:
            self.cursor_revision += 1
            self.cursor_value = checkpoint
        return self.get_cursor(project_id, installation_id)

    def record_dead_letter(self, **kwargs: object) -> int:
        if self.dead_letter_failure:
            raise RuntimeError("dead-letter store unavailable")
        self.dead_letters += 1
        return self.dead_letters

    def record_audit(self, **kwargs: object) -> None:
        self.audit_events.append(kwargs)

    def list_audit(self, project_id: str, *, limit: int = 50) -> list[dict[str, object]]:
        return []


class EvidenceFake:
    def __init__(self) -> None:
        self.requests: list[object] = []

    async def put(self, request: object, content: object, **kwargs: object) -> EvidenceReceipt:
        self.requests.append(request)
        return EvidenceReceipt("ev_" + "a" * 22, "".join(["0"] * 64), 1, "application/json", False)


class FailingEvidenceFake(EvidenceFake):
    async def put(self, request: object, content: object, **kwargs: object) -> EvidenceReceipt:
        from projecta_api.evidence.ports import EvidenceError

        raise EvidenceError("EVIDENCE_WRITE_INTERRUPTED")


class SourceFake:
    def __init__(self) -> None:
        self.calls = 0

    async def commit_source(self, event: object, evidence: object) -> None:
        self.calls += 1


@pytest.mark.asyncio
async def test_single_attempt_commits_one_cursor_and_replays_same_operation() -> None:
    repository = InMemoryRepository()
    registry = ConnectorRegistry()
    adapter = JsonMockAdapter(fixture())
    registry.register(adapter)
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-a", allowed_projects=("project-a",)),
        repository,
        repository,
    )
    source = SourceFake()
    evidence = EvidenceFake()
    orchestrator = ConnectorSyncOrchestrator(
        repository, policy, registry, cast(object, evidence), source
    )
    context = TrustedActorContext("actor-a", "request-a", "operation-a")
    command = SyncCommand(
        projectId="project-a",
        installationId="install-a",
        expectedInstallationRevision=1,
        idempotencyKey="operation-123456789",
        runId="run-a",
        deadline=NOW + timedelta(minutes=1),
        capability="inbound-import",
    )
    result = await orchestrator.run(context, command)
    replay = await orchestrator.run(context, command)
    assert result.outcome == "succeeded"
    assert replay.outcome == "replayed"
    assert adapter.pull_call_count == 1
    assert source.calls == 1
    assert repository.cursor_revision == 1
    request = cast(EvidencePutRequest, evidence.requests[0])
    assert len(request.declared_sha256) == 64
    assert not request.declared_sha256.startswith("sha256:")
    stored_hashes = [body_hash for body_hash, _ in repository.events.values()]
    assert stored_hashes and all(len(body_hash) == 64 for body_hash in stored_hashes)
    assert all(not body_hash.startswith("sha256:") for body_hash in stored_hashes)


@pytest.mark.asyncio
async def test_sync_telemetry_has_one_safe_start_and_terminal_event() -> None:
    repository = InMemoryRepository()
    registry = ConnectorRegistry()
    registry.register(JsonMockAdapter(fixture()))
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-a", allowed_projects=("project-a",)),
        repository,
        repository,
    )
    telemetry = InMemoryConnectorTelemetry()
    orchestrator = ConnectorSyncOrchestrator(
        repository,
        policy,
        registry,
        cast(object, EvidenceFake()),
        SourceFake(),
        telemetry=telemetry,
    )
    command = SyncCommand(
        projectId="project-a",
        installationId="install-a",
        expectedInstallationRevision=1,
        idempotencyKey="telemetry-operation-1",
        runId="run-telemetry",
        deadline=NOW + timedelta(minutes=1),
        capability="inbound-import",
    )

    await orchestrator.run(
        TrustedActorContext("actor-a", "request-telemetry", "operation-telemetry"), command
    )

    assert [event.phase for event in telemetry.events] == ["start", "terminal"]
    assert telemetry.events[0].project_scope != "project-a"
    assert telemetry.events[1].outcome == "succeeded"
    assert telemetry.events[1].event_count == 1
    assert [event["operation"] for event in repository.audit_events] == ["run", "run"]


@pytest.mark.asyncio
async def test_evidence_failure_is_sanitized_and_leaves_a_terminal_run() -> None:
    repository = InMemoryRepository()
    registry = ConnectorRegistry()
    registry.register(JsonMockAdapter(fixture()))
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-a", allowed_projects=("project-a",)),
        repository,
        repository,
    )
    orchestrator = ConnectorSyncOrchestrator(
        repository,
        policy,
        registry,
        cast(object, FailingEvidenceFake()),
        SourceFake(),
    )
    command = SyncCommand(
        projectId="project-a",
        installationId="install-a",
        expectedInstallationRevision=1,
        idempotencyKey="evidence-failure-1",
        runId="run-evidence-failure",
        deadline=NOW + timedelta(minutes=1),
        capability="inbound-import",
    )

    result = await orchestrator.run(
        TrustedActorContext("actor-a", "request-evidence", "operation-evidence"),
        command,
    )

    assert result.outcome == "failed"
    assert result.failure_code == "EVIDENCE_WRITE_FAILED"
    assert repository.runs[command.run_id].terminal_at is not None
    assert repository.events == {}


@pytest.mark.asyncio
async def test_installation_service_rechecks_capability_revision_and_audits_lifecycle() -> None:
    repository = InMemoryRepository()
    registry = ConnectorRegistry()
    registry.register(JsonMockAdapter(fixture()))
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-a", allowed_projects=("project-a",)),
        repository,
        repository,
    )
    service = ConnectorInstallationService(repository, policy, registry)
    context = TrustedActorContext("actor-a", "request-install", "operation-install")
    created = await service.create(
        context,
        InstallationMutation(
            installationId="install-new",
            projectId="project-a",
            connectorType="json-mock",
            fixtureReference="fixture://project-a",
        ),
    )
    assert created.enabled is False and created.secret_configured is False
    enabled = await service.enable(context, "project-a", "install-new", created.revision)
    assert enabled.enabled is True and enabled.revision == created.revision + 1
    read = await service.read(context, "project-a", "install-new")
    assert read.revision == enabled.revision


@pytest.mark.asyncio
async def test_source_failure_is_terminal_dead_lettered_and_explicit_retry_uses_new_key() -> None:
    repository = InMemoryRepository()
    registry = ConnectorRegistry()
    adapter = JsonMockAdapter(fixture())
    registry.register(adapter)
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-a", allowed_projects=("project-a",)),
        repository,
        repository,
    )

    class FlakySource(SourceFake):
        def __init__(self) -> None:
            super().__init__()
            self.fail = True

        async def commit_source(self, event: object, evidence: object) -> None:
            if self.fail:
                self.fail = False
                raise RuntimeError("provider payload must not escape")
            await super().commit_source(event, evidence)

    source = FlakySource()
    orchestrator = ConnectorSyncOrchestrator(
        repository, policy, registry, cast(object, EvidenceFake()), source
    )
    context = TrustedActorContext("actor-a", "request-retry", "operation-retry")
    first = SyncCommand(
        projectId="project-a",
        installationId="install-a",
        expectedInstallationRevision=1,
        idempotencyKey="operation-first-123",
        runId="run-first",
        deadline=NOW + timedelta(minutes=1),
        capability="inbound-import",
    )
    failed = await orchestrator.run(context, first)
    assert failed.outcome == "failed" and failed.dead_letter_id == 1
    retry = SyncCommand(
        projectId="project-a",
        installationId="install-a",
        expectedInstallationRevision=1,
        idempotencyKey="operation-retry-123",
        runId="run-retry",
        deadline=NOW + timedelta(minutes=1),
        capability="inbound-import",
        retry={"parentRunId": "run-first", "parentRevision": 2, "attemptNumber": 2},
    )
    succeeded = await orchestrator.retry(context, retry)
    assert succeeded.outcome == "succeeded"
    assert source.calls == 1
    assert repository.cursor_revision == 1


@pytest.mark.asyncio
async def test_dead_letter_store_failure_still_finishes_run_without_false_success() -> None:
    repository = InMemoryRepository()
    repository.dead_letter_failure = True
    registry = ConnectorRegistry()
    registry.register(JsonMockAdapter(fixture()))
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-a", allowed_projects=("project-a",)),
        repository,
        repository,
    )

    class FailingSource(SourceFake):
        async def commit_source(self, event: object, evidence: object) -> None:
            raise RuntimeError("semantic core unavailable")

    orchestrator = ConnectorSyncOrchestrator(
        repository, policy, registry, cast(object, EvidenceFake()), FailingSource()
    )
    command = SyncCommand(
        projectId="project-a",
        installationId="install-a",
        expectedInstallationRevision=1,
        idempotencyKey="dead-letter-failure-1",
        runId="run-dl-failure",
        deadline=NOW + timedelta(minutes=1),
        capability="inbound-import",
    )

    result = await orchestrator.run(
        TrustedActorContext("actor-a", "request-dl", "operation-dl"), command
    )

    assert result.outcome == "failed"
    assert result.dead_letter_id is None
    assert repository.runs["run-dl-failure"].terminal_outcome == "failed"
    assert repository.cursor_revision == 0
