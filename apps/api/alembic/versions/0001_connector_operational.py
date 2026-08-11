"""Create connector operational state tables.

Revision ID: 0001_connector_operational
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_connector_operational"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_installations",
        sa.Column("installation_id", sa.String(128), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("connector_type", sa.String(64), nullable=False),
        sa.Column("capability_snapshot", sa.JSON(), nullable=False),
        sa.Column("secret_reference", sa.String(512), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("installation_id", name="pk_connector_installations"),
        sa.UniqueConstraint(
            "project_id", "installation_id", name="uq_connector_installations_project_installation"
        ),
        sa.UniqueConstraint(
            "project_id", "connector_type", name="uq_connector_installations_project_connector"
        ),
    )
    op.create_table(
        "connector_event_inbox",
        sa.Column("event_id", sa.String(256), nullable=False),
        sa.Column("installation_id", sa.String(128), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column("content_reference", sa.String(512), nullable=False),
        sa.Column("accepted_outcome", sa.String(32), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("conflict_count", sa.Integer(), nullable=False),
        sa.Column("conflict_last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(body_hash) = 64", name="ck_connector_event_inbox_body_hash_sha256"
        ),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["connector_installations.installation_id"],
            name="fk_event_installation",
        ),
        sa.PrimaryKeyConstraint(
            "event_id", "installation_id", "project_id", name="pk_connector_event_inbox"
        ),
    )
    op.create_index(
        "ix_connector_event_inbox_project_installation",
        "connector_event_inbox",
        ["project_id", "installation_id"],
    )
    op.create_table(
        "connector_sync_runs",
        sa.Column("run_id", sa.String(128), nullable=False),
        sa.Column("installation_id", sa.String(128), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_outcome", sa.String(32), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("replay_count", sa.Integer(), nullable=False),
        sa.Column("dead_letter_id", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("retry_of_run_id", sa.String(128), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(terminal_at IS NULL AND terminal_outcome IS NULL) OR (terminal_at IS NOT NULL AND terminal_outcome IS NOT NULL)",
            name="ck_connector_sync_runs_terminal_pair",
        ),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["connector_installations.installation_id"],
            name="fk_run_installation",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_run_id"], ["connector_sync_runs.run_id"], name="fk_run_retry"
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_connector_sync_runs"),
        sa.UniqueConstraint(
            "installation_id", "idempotency_key", name="uq_connector_sync_runs_installation_id"
        ),
    )
    op.create_index(
        "ix_connector_sync_runs_project_started",
        "connector_sync_runs",
        ["project_id", "started_at"],
    )
    op.create_table(
        "connector_sync_attempts",
        sa.Column("run_id", sa.String(128), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["connector_sync_runs.run_id"], name="fk_attempt_run"),
        sa.PrimaryKeyConstraint("run_id", "attempt_number", name="pk_connector_sync_attempts"),
    )
    op.create_index("ix_connector_sync_attempts_run", "connector_sync_attempts", ["run_id"])
    op.create_table(
        "connector_cursors",
        sa.Column("installation_id", sa.String(128), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("checkpoint", sa.String(512), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["connector_installations.installation_id"],
            name="fk_cursor_installation",
        ),
        sa.PrimaryKeyConstraint("installation_id", name="pk_connector_cursors"),
    )
    op.create_table(
        "connector_dead_letters",
        sa.Column("dead_letter_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.String(128), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("run_id", sa.String(128), nullable=True),
        sa.Column("event_id", sa.String(256), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=False),
        sa.Column("sanitized_detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id", "installation_id", "project_id"],
            [
                "connector_event_inbox.event_id",
                "connector_event_inbox.installation_id",
                "connector_event_inbox.project_id",
            ],
            name="fk_dead_event_scope",
        ),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["connector_installations.installation_id"],
            name="fk_dead_installation",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["connector_sync_runs.run_id"], name="fk_dead_run"),
        sa.PrimaryKeyConstraint("dead_letter_id", name="pk_connector_dead_letters"),
    )
    op.create_index(
        "ix_connector_dead_letters_project_created",
        "connector_dead_letters",
        ["project_id", "created_at"],
    )
    op.create_table(
        "connector_audit_records",
        sa.Column("audit_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("installation_id", sa.String(128), nullable=True),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("actor_reference", sa.String(256), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["connector_installations.installation_id"],
            name="fk_audit_installation",
        ),
        sa.PrimaryKeyConstraint("audit_id", name="pk_connector_audit_records"),
    )
    op.create_index(
        "ix_connector_audit_project_recorded",
        "connector_audit_records",
        ["project_id", "recorded_at"],
    )


def downgrade() -> None:
    """Rollback is intentionally a destructive operator action, not app startup."""
    op.drop_index("ix_connector_audit_project_recorded", table_name="connector_audit_records")
    op.drop_table("connector_audit_records")
    op.drop_index("ix_connector_dead_letters_project_created", table_name="connector_dead_letters")
    op.drop_table("connector_dead_letters")
    op.drop_table("connector_cursors")
    op.drop_index("ix_connector_sync_attempts_run", table_name="connector_sync_attempts")
    op.drop_table("connector_sync_attempts")
    op.drop_index("ix_connector_sync_runs_project_started", table_name="connector_sync_runs")
    op.drop_table("connector_sync_runs")
    op.drop_index(
        "ix_connector_event_inbox_project_installation", table_name="connector_event_inbox"
    )
    op.drop_table("connector_event_inbox")
    op.drop_table("connector_installations")
