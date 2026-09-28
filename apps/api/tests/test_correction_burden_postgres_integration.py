"""Live PostgreSQL checks for RM-65 telemetry custody and append-only storage."""

from __future__ import annotations

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from projecta_api.config import Settings
from projecta_api.extraction.correction_burden import (
    CorrectionBurdenRequest,
    CorrectionBurdenTelemetryService,
    PostgresCorrectionBurdenRepository,
)
from projecta_api.operational.database import ConnectorDatabase

pytestmark = pytest.mark.postgres_integration


@pytest.fixture()
def database() -> Generator[ConnectorDatabase, None, None]:
    if os.getenv("PROJECTA_CONNECTOR_INTEGRATION") != "1":
        pytest.skip("Compose PostgreSQL integration is opt-in")
    database = ConnectorDatabase(Settings())
    database.check_ready()
    yield database
    database.dispose()


def _request(project_id: str, idempotency_key: str) -> CorrectionBurdenRequest:
    digest = "sha256:" + "b" * 64
    return CorrectionBurdenRequest.model_validate(
        {
            "projectId": project_id,
            "itemKind": "entity",
            "itemId": "eh1_opaque-candidate",
            "assertionId": "assertion_opaque-1",
            "sourceVersionId": "sv_" + "a" * 64,
            "sourceVersionRevision": 1,
            "reviewReceiptDigest": digest,
            "materializationRevision": digest,
            "inferenceRevision": digest,
            "correctionCategory": "unchanged",
            "correctionDimensions": [],
            "reviewOutcome": "confirmed",
            "semanticEditCount": 0,
            "reviewLatencyMs": 1000,
            "materializationState": "accepted",
            "inferenceState": "current",
            "idempotencyKey": idempotency_key,
        }
    )


def test_postgres_correction_burden_is_idempotent_and_append_only(
    database: ConnectorDatabase,
) -> None:
    project = "integration-" + uuid4().hex[:12]
    service = CorrectionBurdenTelemetryService(PostgresCorrectionBurdenRepository(database))
    first = service.record(_request(project, "telemetry-1"))
    replay = service.record(_request(project, "telemetry-1"))

    assert first.outcome == "accepted"
    assert replay.outcome == "replayed"
    assert replay.event_digest == first.event_digest

    with database.engine.begin() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(
                text(
                    "UPDATE correction_burden_events "
                    "SET semantic_edit_count = 1 WHERE event_id = :event_id"
                ),
                {"event_id": first.event_id},
            )
    with database.engine.begin() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(
                text("DELETE FROM correction_burden_events WHERE event_id = :event_id"),
                {"event_id": first.event_id},
            )
    with database.engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM correction_burden_events WHERE event_id = :event_id"),
            {"event_id": first.event_id},
        ).scalar_one()
    assert count == 1
