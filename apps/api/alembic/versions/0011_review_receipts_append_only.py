"""Enforce append-only review decision receipt history in PostgreSQL."""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_review_receipts_append_only"
down_revision: str | None = "0010_correction_burden_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION reject_review_decision_receipt_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'review_decision_receipts is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER review_decision_receipts_append_only
        BEFORE UPDATE OR DELETE ON review_decision_receipts
        FOR EACH ROW EXECUTE FUNCTION reject_review_decision_receipt_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER review_decision_receipts_append_only ON review_decision_receipts
        """
    )
    op.execute("DROP FUNCTION reject_review_decision_receipt_mutation()")
