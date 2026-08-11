"""Add optimistic revision to sync runs.

Revision ID: 0002_sync_run_revision
Revises: 0001_connector_operational
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_sync_run_revision"
down_revision: str | None = "0001_connector_operational"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The model was released with the revision column in the initial
    # migration, while one intermediate database may still have the legacy
    # shape.  Keep this migration safe for both histories.
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("connector_sync_runs")}
    if "revision" not in columns:
        op.add_column(
            "connector_sync_runs",
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        )
        op.alter_column("connector_sync_runs", "revision", server_default=None)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("connector_sync_runs")}
    if "revision" in columns:
        op.drop_column("connector_sync_runs", "revision")
