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
