"""Add append-only raw-content-free correction-burden telemetry."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_correction_burden_events"
down_revision: str | None = "0009_review_decision_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "correction_burden_events",
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("item_kind", sa.String(32), nullable=False),
        sa.Column("item_digest", sa.String(71), nullable=False),
        sa.Column("assertion_digest", sa.String(71), nullable=False),
        sa.Column("source_version_digest", sa.String(71), nullable=False),
        sa.Column("source_version_revision", sa.Integer(), nullable=False),
        sa.Column("review_receipt_digest", sa.String(71), nullable=False),
        sa.Column("materialization_revision", sa.String(71), nullable=True),
        sa.Column("inference_revision", sa.String(71), nullable=True),
        sa.Column("correction_category", sa.String(16), nullable=False),
        sa.Column("correction_dimensions", sa.JSON(), nullable=False),
        sa.Column("review_outcome", sa.String(32), nullable=False),
        sa.Column("semantic_edit_count", sa.Integer(), nullable=False),
        sa.Column("review_latency_ms", sa.BigInteger(), nullable=False),
        sa.Column("materialization_state", sa.String(32), nullable=False),
        sa.Column("inference_state", sa.String(32), nullable=False),
        sa.Column("idempotency_digest", sa.String(71), nullable=False),
        sa.Column("request_digest", sa.String(71), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_digest", sa.String(71), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_correction_burden_events"),
        sa.UniqueConstraint(
            "project_id", "idempotency_digest", name="uq_correction_burden_project_idempotency"
        ),
        sa.UniqueConstraint("event_digest", name="uq_correction_burden_event_digest"),
    )
    op.create_index(
        "ix_correction_burden_project_occurred",
        "correction_burden_events",
        ["project_id", "occurred_at", "event_id"],
    )
    op.execute(
        """
        CREATE FUNCTION reject_correction_burden_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'correction_burden_events is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER correction_burden_events_append_only
        BEFORE UPDATE OR DELETE ON correction_burden_events
        FOR EACH ROW EXECUTE FUNCTION reject_correction_burden_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER correction_burden_events_append_only ON correction_burden_events"
    )
    op.execute("DROP FUNCTION reject_correction_burden_event_mutation()")
    op.drop_index("ix_correction_burden_project_occurred", table_name="correction_burden_events")
    op.drop_table("correction_burden_events")
