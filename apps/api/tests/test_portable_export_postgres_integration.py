"""Live PostgreSQL checks for portable export receipt and telemetry payloads."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from projecta_api.config import Settings
from projecta_api.extraction.correction_burden import (
    CorrectionBurdenRequest,
    CorrectionBurdenTelemetryService,
    PostgresCorrectionBurdenRepository,
)
from projecta_api.extraction.review_receipts import (
    PostgresReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
)
from projecta_api.operational.database import ConnectorDatabase
from projecta_api.portable_export import PortableExportFailure, _write_postgres_payloads

pytestmark = pytest.mark.postgres_integration


@pytest.fixture()
def database() -> Generator[ConnectorDatabase, None, None]:
    if os.getenv("PROJECTA_CONNECTOR_INTEGRATION") != "1":
        pytest.skip("Compose PostgreSQL integration is opt-in")
    database = ConnectorDatabase(Settings())
    database.check_ready()
    yield database
    database.dispose()


def _actor(project_id: str) -> ReviewActorContext:
    return ReviewActorContext(
        project_id=project_id,
        actor_id="integration-reviewer",
        capability="candidate.review",
        authorization_revision="membership-1",
    )


def _receipt_request(project_id: str) -> ReviewDecisionRequest:
    return ReviewDecisionRequest.model_validate(
        {
            "projectId": project_id,
            "itemKind": "entity",
            "itemHandle": "eh1_" + "a" * 64,
            "candidateRevision": 1,
            "expectedCandidateRevision": 0,
            "sourceVersionId": "sv_" + "b" * 64,
            "sourceVersionRevision": 1,
            "constrainedContractVersion": "entity-handle.v1",
            "idempotencyKey": "export-integration-review-1",
            "decision": "confirm",
        }
    )


def _telemetry_request(project_id: str, receipt_digest: str) -> CorrectionBurdenRequest:
    revision = "sha256:" + "b" * 64
    return CorrectionBurdenRequest.model_validate(
        {
            "projectId": project_id,
            "itemKind": "entity",
            "itemId": "eh1_opaque-candidate",
            "assertionId": "assertion_opaque-1",
            "sourceVersionId": "sv_" + "a" * 64,
            "sourceVersionRevision": 1,
            "reviewReceiptDigest": receipt_digest,
            "materializationRevision": revision,
            "inferenceRevision": revision,
            "correctionCategory": "unchanged",
            "correctionDimensions": [],
            "reviewOutcome": "confirmed",
            "semanticEditCount": 0,
            "reviewLatencyMs": 1000,
            "materializationState": "accepted",
            "inferenceState": "current",
            "idempotencyKey": "export-integration-telemetry-1",
        }
    )


def test_export_payloads_reload_receipt_and_correction_entities(
    database: ConnectorDatabase, tmp_path: Path
) -> None:
    """A valid receipt plus its correction event must export as validated JSONL.

    Regression: the export read both entities through the Core Connection, which
    materialized plain column rows, so ``receipt_from_row`` received a ``receipt_id``
    string and a project holding one recorded receipt was refused with
    ``EXPORT_INTEGRITY_FAILED`` instead of producing a portable package.
    """
    project = "integration-" + uuid4().hex[:12]
    receipt = ReviewDecisionReceiptService(
        PostgresReviewDecisionReceiptRepository(database)
    ).record(_actor(project), _receipt_request(project))
    event = CorrectionBurdenTelemetryService(PostgresCorrectionBurdenRepository(database)).record(
        _telemetry_request(project, receipt.receipt_digest)
    )

    connectors = tmp_path / "connectors.json"
    receipts = tmp_path / "review-decision-receipts.jsonl"
    corrections = tmp_path / "correction-burden-events.jsonl"
    result = _write_postgres_payloads(database.engine, project, connectors, receipts, corrections)

    assert result["record_counts"]["reviewReceipts"] == 1
    assert result["record_counts"]["correctionBurdenEvents"] == 1
    exported_receipt = json.loads(receipts.read_text(encoding="utf-8").strip())
    exported_event = json.loads(corrections.read_text(encoding="utf-8").strip())
    assert exported_receipt["receiptId"] == receipt.receipt_id
    assert exported_receipt["receiptDigest"] == receipt.receipt_digest
    assert exported_receipt["projectId"] == project
    assert exported_receipt["sequence"] == 1
    assert exported_event["eventId"] == event.event_id
    assert exported_event["reviewReceiptDigest"] == receipt.receipt_digest
    assert receipt.receipt_digest in result["receipt_digests"]


def test_export_refuses_a_receipt_whose_stored_digest_was_tampered(
    database: ConnectorDatabase, tmp_path: Path
) -> None:
    """Out-of-band corruption of a stored receipt digest must still refuse the export."""
    project = "integration-" + uuid4().hex[:12]
    receipt = ReviewDecisionReceiptService(
        PostgresReviewDecisionReceiptRepository(database)
    ).record(_actor(project), _receipt_request(project))
    tampered = "sha256:" + hashlib.sha256(receipt.receipt_id.encode("utf-8")).hexdigest()
    with database.connection(operation="tamper_review_decision_receipt") as connection:
        connection.execute(
            text(
                "ALTER TABLE review_decision_receipts "
                "DISABLE TRIGGER review_decision_receipts_append_only"
            )
        )
        changed = connection.execute(
            text(
                "UPDATE review_decision_receipts SET receipt_digest = :digest "
                "WHERE receipt_id = :receipt_id"
            ),
            {"digest": tampered, "receipt_id": receipt.receipt_id},
        ).rowcount
        connection.execute(
            text(
                "ALTER TABLE review_decision_receipts "
                "ENABLE TRIGGER review_decision_receipts_append_only"
            )
        )
    assert changed == 1

    receipts = tmp_path / "review-decision-receipts.jsonl"
    with pytest.raises(PortableExportFailure, match="EXPORT_INTEGRITY_FAILED"):
        _write_postgres_payloads(
            database.engine,
            project,
            tmp_path / "connectors.json",
            receipts,
            tmp_path / "correction-burden-events.jsonl",
        )
