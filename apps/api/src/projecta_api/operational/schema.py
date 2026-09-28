"""SQLAlchemy metadata for connector-only PostgreSQL operational state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


Timestamp = DateTime(timezone=True)


class ConnectorInstallation(Base):
    __tablename__ = "connector_installations"
    __table_args__ = (
        UniqueConstraint("project_id", "connector_type"),
        UniqueConstraint("project_id", "installation_id"),
    )

    installation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    secret_reference: Mapped[str | None] = mapped_column(String(512))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)


class TeamsSetupHandle(Base):
    __tablename__ = "teams_setup_handles"
    __table_args__ = (Index("ix_teams_setup_project_expiry", "project_id", "expires_at"),)

    setup_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    installation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    expected_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(Timestamp)
    created_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)


class GitHubPublicIssuesSetupHandle(Base):
    __tablename__ = "github_public_issues_setup_handles"
    __table_args__ = (
        Index("ix_github_public_issues_setup_project_expiry", "project_id", "expires_at"),
        Index(
            "ix_github_public_issues_setup_actor_revision",
            "project_id",
            "actor_id",
            "expected_revision",
        ),
    )

    setup_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    installation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    expected_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(Timestamp)
    created_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)


class ConnectorEventInbox(Base):
    __tablename__ = "connector_event_inbox"
    __table_args__ = (
        Index("ix_connector_event_inbox_project_installation", "project_id", "installation_id"),
        CheckConstraint("length(body_hash) = 64", name="body_hash_sha256"),
    )

    event_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    installation_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("connector_installations.installation_id"), primary_key=True
    )
    project_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    accepted_outcome: Mapped[str | None] = mapped_column(String(32))
    accepted_at: Mapped[datetime | None] = mapped_column(Timestamp)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_last_seen_at: Mapped[datetime | None] = mapped_column(Timestamp)
    created_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)


class ConnectorSyncRun(Base):
    __tablename__ = "connector_sync_runs"
    __table_args__ = (
        UniqueConstraint("installation_id", "idempotency_key"),
        Index("ix_connector_sync_runs_project_started", "project_id", "started_at"),
        CheckConstraint(
            "(terminal_at IS NULL AND terminal_outcome IS NULL) OR "
            "(terminal_at IS NOT NULL AND terminal_outcome IS NOT NULL)",
            name="terminal_pair",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    installation_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("connector_installations.installation_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    terminal_at: Mapped[datetime | None] = mapped_column(Timestamp)
    terminal_outcome: Mapped[str | None] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    replay_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dead_letter_id: Mapped[int | None] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    retry_of_run_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("connector_sync_runs.run_id")
    )
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)


class ConnectorSyncAttempt(Base):
    __tablename__ = "connector_sync_attempts"
    __table_args__ = (Index("ix_connector_sync_attempts_run", "run_id"),)

    run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("connector_sync_runs.run_id"), primary_key=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    terminal_at: Mapped[datetime | None] = mapped_column(Timestamp)
    outcome: Mapped[str | None] = mapped_column(String(32))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_detail: Mapped[str | None] = mapped_column(Text)


class ConnectorCursor(Base):
    __tablename__ = "connector_cursors"

    installation_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("connector_installations.installation_id"), primary_key=True
    )
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    checkpoint: Mapped[str | None] = mapped_column(String(512))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)


class ConnectorDeadLetter(Base):
    __tablename__ = "connector_dead_letters"
    __table_args__ = (
        Index("ix_connector_dead_letters_project_created", "project_id", "created_at"),
        ForeignKeyConstraint(
            ["event_id", "installation_id", "project_id"],
            [
                "connector_event_inbox.event_id",
                "connector_event_inbox.installation_id",
                "connector_event_inbox.project_id",
            ],
            name="fk_dead_event_scope",
        ),
    )

    dead_letter_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    installation_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("connector_installations.installation_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("connector_sync_runs.run_id"))
    event_id: Mapped[str | None] = mapped_column(String(256))
    failure_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sanitized_detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(Timestamp)


class ConnectorAuditRecord(Base):
    __tablename__ = "connector_audit_records"
    __table_args__ = (Index("ix_connector_audit_project_recorded", "project_id", "recorded_at"),)

    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    installation_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("connector_installations.installation_id")
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(256), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    revision: Mapped[int | None] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)


class ReviewDecisionReceipt(Base):
    """Append-only, raw-content-free human review decision custody."""

    __tablename__ = "review_decision_receipts"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_digest"),
        UniqueConstraint("project_id", "item_kind", "item_handle_digest", "sequence"),
        Index(
            "ix_review_decision_receipts_project_item_sequence",
            "project_id",
            "item_kind",
            "item_handle_digest",
            "sequence",
        ),
    )

    receipt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    authorization_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    item_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    item_handle_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    candidate_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source_version_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    source_version_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    constrained_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_digest: Mapped[str | None] = mapped_column(String(71))
    previous_decision_digest: Mapped[str | None] = mapped_column(String(71))
    idempotency_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    receipt_digest: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)


class CorrectionBurdenEvent(Base):
    """Append-only, raw-content-free correction-burden telemetry."""

    __tablename__ = "correction_burden_events"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_digest"),
        UniqueConstraint("event_digest"),
        Index("ix_correction_burden_project_occurred", "project_id", "occurred_at", "event_id"),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    item_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    item_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    assertion_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    source_version_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    source_version_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    review_receipt_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    materialization_revision: Mapped[str | None] = mapped_column(String(71))
    inference_revision: Mapped[str | None] = mapped_column(String(71))
    correction_category: Mapped[str] = mapped_column(String(16), nullable=False)
    correction_dimensions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    review_outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    semantic_edit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    review_latency_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    materialization_state: Mapped[str] = mapped_column(String(32), nullable=False)
    inference_state: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False)
    event_digest: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)
