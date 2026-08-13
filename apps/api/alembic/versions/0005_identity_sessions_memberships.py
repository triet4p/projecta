"""Add Projecta-owned OIDC session, login-state, and membership tables.

Revision ID: 0005_identity_sessions
Revises: 0004_scoped_event_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_identity_sessions"
down_revision: str | None = "0004_scoped_event_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projecta_oidc_login_attempts",
        sa.Column("state", sa.String(256), primary_key=True),
        sa.Column("nonce", sa.String(256), nullable=False),
        sa.Column("code_verifier", sa.String(256), nullable=False),
        sa.Column("return_path", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
    )
    op.create_index("ix_projecta_oidc_login_attempts_expires", "projecta_oidc_login_attempts", ["expires_at"])
    op.create_table(
        "projecta_sessions",
        sa.Column("session_id", sa.String(256), primary_key=True),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("actor_id", sa.String(256), nullable=False),
        sa.Column("tenant_id", sa.String(128)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("csrf_token", sa.String(256), nullable=False),
        sa.Column("session_epoch", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_projecta_sessions_subject", "projecta_sessions", ["subject"])
    op.create_table(
        "projecta_project_memberships",
        sa.Column("subject", sa.String(256), primary_key=True),
        sa.Column("project_id", sa.String(128), primary_key=True),
        sa.Column("roles", sa.ARRAY(sa.String(32)), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projecta_memberships_project", "projecta_project_memberships", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_projecta_memberships_project", table_name="projecta_project_memberships")
    op.drop_table("projecta_project_memberships")
    op.drop_index("ix_projecta_sessions_subject", table_name="projecta_sessions")
    op.drop_table("projecta_sessions")
    op.drop_index("ix_projecta_oidc_login_attempts_expires", table_name="projecta_oidc_login_attempts")
    op.drop_table("projecta_oidc_login_attempts")
