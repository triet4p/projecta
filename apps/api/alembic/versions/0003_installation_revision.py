"""Add optimistic revision to connector installations."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_installation_revision"
down_revision: str | None = "0002_sync_run_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("connector_installations")}
    if "revision" not in columns:
        op.add_column(
            "connector_installations",
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        )
        op.alter_column("connector_installations", "revision", server_default=None)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("connector_installations")}
    if "revision" in columns:
        op.drop_column("connector_installations", "revision")
