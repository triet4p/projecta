"""Add append-only raw-content-free review decision receipts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_review_decision_receipts"
down_revision: str | None = "0008_github_setup_actor_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_decision_receipts",
        sa.Column("receipt_id", sa.String(128), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("actor_digest", sa.String(71), nullable=False),
        sa.Column("authorization_digest", sa.String(71), nullable=False),
        sa.Column("item_kind", sa.String(32), nullable=False),
        sa.Column("item_handle_digest", sa.String(71), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("candidate_revision", sa.Integer(), nullable=False),
        sa.Column("source_version_digest", sa.String(71), nullable=False),
        sa.Column("source_version_revision", sa.Integer(), nullable=False),
        sa.Column("constrained_contract_version", sa.String(64), nullable=False),
        sa.Column("evidence_digest", sa.String(71), nullable=True),
        sa.Column("previous_decision_digest", sa.String(71), nullable=True),
        sa.Column("idempotency_digest", sa.String(71), nullable=False),
        sa.Column("request_digest", sa.String(71), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("receipt_digest", sa.String(71), nullable=False),
        sa.PrimaryKeyConstraint("receipt_id", name="pk_review_decision_receipts"),
        sa.UniqueConstraint("receipt_digest", name="uq_review_decision_receipts_receipt_digest"),
        sa.UniqueConstraint(
            "project_id",
            "idempotency_digest",
            name="uq_review_decision_receipts_project_idempotency",
        ),
        sa.UniqueConstraint(
            "project_id",
            "item_kind",
            "item_handle_digest",
            "sequence",
            name="uq_review_decision_receipts_project_item_sequence",
        ),
    )
    op.create_index(
        "ix_review_decision_receipts_project_item_sequence",
        "review_decision_receipts",
        ["project_id", "item_kind", "item_handle_digest", "sequence"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_review_decision_receipts_project_item_sequence",
        table_name="review_decision_receipts",
    )
    op.drop_table("review_decision_receipts")
