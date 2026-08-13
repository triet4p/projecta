"""Bind GitHub setup handles to the intended actor and mutation revision."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_github_setup_actor_revision"
down_revision: str | None = "0007_github_setup_handles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "github_public_issues_setup_handles",
        sa.Column("actor_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "github_public_issues_setup_handles",
        sa.Column("expected_revision", sa.Integer(), nullable=True),
    )
    # Existing unconsumed handles predate GH-18 binding and must not remain
    # usable under the stronger contract.
    op.execute(
        sa.text(
            "UPDATE github_public_issues_setup_handles "
            "SET actor_id = 'legacy-invalidated', expected_revision = 1, consumed_at = CURRENT_TIMESTAMP "
            "WHERE actor_id IS NULL"
        )
    )
    op.alter_column(
        "github_public_issues_setup_handles",
        "actor_id",
        existing_type=sa.String(128),
        nullable=False,
    )
    op.alter_column(
        "github_public_issues_setup_handles",
        "expected_revision",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        "ix_github_public_issues_setup_actor_revision",
        "github_public_issues_setup_handles",
        ["project_id", "actor_id", "expected_revision"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_github_public_issues_setup_actor_revision",
        table_name="github_public_issues_setup_handles",
    )
    op.drop_column("github_public_issues_setup_handles", "expected_revision")
    op.drop_column("github_public_issues_setup_handles", "actor_id")
