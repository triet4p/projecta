"""PostgreSQL lifecycle, idempotency, concurrency, and rollback evidence."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from projecta_api.config import Settings
from projecta_api.operational import IdempotencyConflict
from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.repository import PostgresConnectorRepository

pytestmark = pytest.mark.postgres_integration


@pytest.fixture()
def repository() -> PostgresConnectorRepository:
    if os.getenv("PROJECTA_CONNECTOR_INTEGRATION") != "1":
        pytest.skip("Compose PostgreSQL integration is opt-in")
    settings = Settings()
    database = ConnectorDatabase(settings)
    database.check_ready()
    yield PostgresConnectorRepository(database)
    database.dispose()


def test_claim_completion_replay_conflict_and_cursor_rollback(
    repository: PostgresConnectorRepository,
) -> None:
    project = "integration-" + uuid4().hex[:12]
    installation = "install-" + uuid4().hex[:12]
    repository.upsert_installation(
        project_id=project,
        installation_id=installation,
        connector_type="json-mock",
        capability_snapshot={"pull": True},
        secret_reference=None,
        enabled=True,
        expected_revision=None,
    )
    event = "event-" + uuid4().hex
    body_hash = "a" * 64

    def claim() -> str:
        return repository.claim_event(
            project_id=project,
            installation_id=installation,
            event_id=event,
            body_hash=body_hash,
            content_reference="ev_test",
        ).outcome

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(lambda _: claim(), range(2)))
    assert outcomes == ["in_progress", "new"]

    cursor = repository.complete_event(
        project_id=project,
        installation_id=installation,
        event_id=event,
        body_hash=body_hash,
        outcome="accepted",
        checkpoint="opaque-1",
        expected_cursor_revision=0,
    )
    assert cursor is not None and cursor.revision == 1
    assert (
        repository.claim_event(
            project_id=project,
            installation_id=installation,
            event_id=event,
            body_hash=body_hash,
            content_reference="ignored-on-replay",
        ).outcome
        == "replayed"
    )
    with pytest.raises(IdempotencyConflict):
        repository.claim_event(
            project_id=project,
            installation_id=installation,
            event_id=event,
            body_hash="b" * 64,
            content_reference="ev_conflict",
        )

    other_project = "integration-other-" + uuid4().hex[:12]
    other_installation = "install-other-" + uuid4().hex[:12]
    repository.upsert_installation(
        project_id=other_project,
        installation_id=other_installation,
        connector_type="json-mock",
        capability_snapshot={"capabilities": ["inbound-import"]},
        secret_reference=None,
        enabled=True,
        expected_revision=None,
    )
    assert (
        repository.claim_event(
            project_id=other_project,
            installation_id=other_installation,
            event_id=event,
            body_hash=body_hash,
            content_reference="ev_other_scope",
        ).outcome
        == "new"
    )

    failed_event = "event-" + uuid4().hex
    repository.claim_event(
        project_id=project,
        installation_id=installation,
        event_id=failed_event,
        body_hash="c" * 64,
        content_reference="ev_failed",
    )
    failed_cursor = repository.complete_event(
        project_id=project,
        installation_id=installation,
        event_id=failed_event,
        body_hash="c" * 64,
        outcome="failed",
        checkpoint="must-not-advance",
        expected_cursor_revision=1,
    )
    assert failed_cursor is not None and failed_cursor.revision == 1


def test_run_terminal_outcome_retry_lineage_dead_letter_and_audit(
    repository: PostgresConnectorRepository,
) -> None:
    project = "integration-" + uuid4().hex[:12]
    installation = "install-" + uuid4().hex[:12]
    repository.upsert_installation(
        project_id=project,
        installation_id=installation,
        connector_type="json-mock",
        capability_snapshot={"pull": True},
        secret_reference="secret-ref-only",
        enabled=True,
        expected_revision=None,
        audit_operation="installation.create",
        actor_reference="actor-safe",
        correlation_id="corr-install",
    )
    run_id = "run-" + uuid4().hex
    run = repository.start_run(
        project_id=project,
        installation_id=installation,
        run_id=run_id,
        idempotency_key="operation-" + uuid4().hex,
    )
    finished = repository.finish_run(
        project_id=project,
        installation_id=installation,
        run_id=run.run_id,
        outcome="failed",
        failure_code="EVIDENCE_UNAVAILABLE",
        failure_detail="bounded safe failure",
        event_count=3,
        replay_count=1,
    )
    assert finished.terminal_outcome == "failed"
    assert finished.event_count == 3
    assert finished.replay_count == 1
    assert (
        repository.finish_run(
            project_id=project,
            installation_id=installation,
            run_id=run.run_id,
            outcome="accepted",
        ).terminal_outcome
        == "failed"
    )
    dead_letter_id = repository.record_dead_letter(
        project_id=project,
        installation_id=installation,
        run_id=run.run_id,
        failure_code="EVIDENCE_UNAVAILABLE",
        sanitized_detail="bounded safe failure",
    )
    assert dead_letter_id > 0
    repository.record_audit(
        project_id=project,
        installation_id=installation,
        operation="run",
        outcome="failed",
        actor_reference="actor-safe",
        correlation_id="corr-safe",
        revision=1,
    )
    assert repository.list_audit(project, limit=500)[0]["correlationId"] == "corr-safe"
    assert any(
        row["correlationId"] == "corr-install" for row in repository.list_audit(project, limit=500)
    )
