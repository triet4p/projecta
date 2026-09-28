"""Optional PostgreSQL integration checks for RM-61 custody."""

from __future__ import annotations

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from projecta_api.config import Settings
from projecta_api.extraction.review_receipts import (
    PostgresReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
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


@pytest.fixture()
def service(database: ConnectorDatabase) -> ReviewDecisionReceiptService:
    return ReviewDecisionReceiptService(PostgresReviewDecisionReceiptRepository(database))


def test_postgres_review_receipt_is_append_only_and_idempotent(
    service: ReviewDecisionReceiptService,
) -> None:
    project = "integration-" + uuid4().hex[:12]
    actor = ReviewActorContext(
        project_id=project,
        actor_id="integration-reviewer",
        capability="candidate.review",
        authorization_revision="membership-1",
    )
    request = ReviewDecisionRequest(
        projectId=project,
        itemKind="entity",
        itemHandle="eh1_" + "a" * 64,
        candidateRevision=1,
        expectedCandidateRevision=0,
        sourceVersionId="sv_" + "b" * 64,
        sourceVersionRevision=1,
        constrainedContractVersion="entity-handle.v1",
        idempotencyKey="integration-review-1",
        decision="confirm",
    )
    first = service.record(actor, request)
    replay = service.record(actor, request)
    assert first.outcome == "accepted"
    assert replay.outcome == "replayed"
    assert replay.receipt_digest == first.receipt_digest


def test_postgres_review_receipt_row_is_immutable(
    service: ReviewDecisionReceiptService,
    database: ConnectorDatabase,
) -> None:
    project = "integration-" + uuid4().hex[:12]
    actor = ReviewActorContext(
        project_id=project,
        actor_id="integration-reviewer",
        capability="candidate.review",
        authorization_revision="membership-1",
    )
    request = ReviewDecisionRequest(
        projectId=project,
        itemKind="entity",
        itemHandle="eh1_" + "c" * 64,
        candidateRevision=1,
        expectedCandidateRevision=0,
        sourceVersionId="sv_" + "d" * 64,
        sourceVersionRevision=1,
        constrainedContractVersion="entity-handle.v1",
        idempotencyKey="integration-review-immutable-1",
        decision="confirm",
    )
    first = service.record(actor, request)

    with database.engine.begin() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(
                text(
                    "UPDATE review_decision_receipts SET decision = 'reject' "
                    "WHERE receipt_id = :receipt_id"
                ),
                {"receipt_id": first.receipt_id},
            )
    with database.engine.begin() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(
                text("DELETE FROM review_decision_receipts WHERE receipt_id = :receipt_id"),
                {"receipt_id": first.receipt_id},
            )
    with database.engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM review_decision_receipts WHERE receipt_id = :receipt_id"),
            {"receipt_id": first.receipt_id},
        ).scalar_one()
    assert count == 1
