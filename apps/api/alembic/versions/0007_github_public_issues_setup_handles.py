"""Add single-use GitHub Public Issues setup handles."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_github_setup_handles"
down_revision: str | None = "0006_teams_setup_handles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "github_public_issues_setup_handles",
        sa.Column("setup_hash", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("installation_id", sa.String(128), nullable=False),
        sa.Column("provider_config", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(setup_hash) = 64", name="ck_github_public_issues_setup_hash_sha256"
        ),
    )
    op.create_index(
        "ix_github_public_issues_setup_project_expiry",
        "github_public_issues_setup_handles",
        ["project_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_github_public_issues_setup_project_expiry",
        table_name="github_public_issues_setup_handles",
    )
    op.drop_table("github_public_issues_setup_handles")
