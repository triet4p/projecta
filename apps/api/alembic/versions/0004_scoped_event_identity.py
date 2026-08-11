"""Scope event identity and persist truthful run summaries.

Revision ID: 0004_scoped_event_identity
Revises: 0003_installation_revision
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_scoped_event_identity"
down_revision: str | None = "0003_installation_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    installation_uniques = {
        tuple(constraint.get("column_names") or ())
        for constraint in inspector.get_unique_constraints("connector_installations")
    }
    if ("project_id", "installation_id") not in installation_uniques:
        op.create_unique_constraint(
            "uq_connector_installations_project_installation",
            "connector_installations",
            ["project_id", "installation_id"],
        )

    run_columns = {
        column["name"] for column in inspector.get_columns("connector_sync_runs")
    }
    if "replay_count" not in run_columns:
        op.add_column(
            "connector_sync_runs",
            sa.Column("replay_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("connector_sync_runs", "replay_count", server_default=None)
    if "dead_letter_id" not in run_columns:
        op.add_column(
            "connector_sync_runs",
            sa.Column("dead_letter_id", sa.BigInteger(), nullable=True),
        )

    dead_foreign_keys = inspector.get_foreign_keys("connector_dead_letters")
    event_foreign_keys = [
        foreign_key
        for foreign_key in dead_foreign_keys
        if foreign_key.get("referred_table") == "connector_event_inbox"
    ]
    for foreign_key in event_foreign_keys:
        name = foreign_key.get("name")
        if name and tuple(foreign_key.get("constrained_columns") or ()) != (
            "event_id",
            "installation_id",
            "project_id",
        ):
            op.drop_constraint(name, "connector_dead_letters", type_="foreignkey")

    primary_key = inspector.get_pk_constraint("connector_event_inbox")
    primary_columns = tuple(primary_key.get("constrained_columns") or ())
    if primary_columns != ("event_id", "installation_id", "project_id"):
        primary_name = primary_key.get("name")
        if primary_name:
            op.drop_constraint(primary_name, "connector_event_inbox", type_="primary")
        op.create_primary_key(
            "pk_connector_event_inbox",
            "connector_event_inbox",
            ["event_id", "installation_id", "project_id"],
        )

    has_scoped_event_fk = any(
        tuple(foreign_key.get("constrained_columns") or ())
        == ("event_id", "installation_id", "project_id")
        for foreign_key in event_foreign_keys
    )
    if not has_scoped_event_fk:
        op.create_foreign_key(
            "fk_dead_event_scope",
            "connector_dead_letters",
            "connector_event_inbox",
            ["event_id", "installation_id", "project_id"],
            ["event_id", "installation_id", "project_id"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys("connector_dead_letters"):
        if (
            foreign_key.get("name") == "fk_dead_event_scope"
            and foreign_key.get("name") is not None
        ):
            op.drop_constraint(
                foreign_key["name"], "connector_dead_letters", type_="foreignkey"
            )
    primary_key = inspector.get_pk_constraint("connector_event_inbox")
    primary_name = primary_key.get("name")
    if primary_name:
        op.drop_constraint(primary_name, "connector_event_inbox", type_="primary")
    op.create_primary_key(
        "pk_connector_event_inbox", "connector_event_inbox", ["event_id"]
    )
    op.create_foreign_key(
        "fk_dead_event",
        "connector_dead_letters",
        "connector_event_inbox",
        ["event_id"],
        ["event_id"],
    )
    run_columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("connector_sync_runs")
    }
    if "dead_letter_id" in run_columns:
        op.drop_column("connector_sync_runs", "dead_letter_id")
    if "replay_count" in run_columns:
        op.drop_column("connector_sync_runs", "replay_count")
    unique_constraints = sa.inspect(op.get_bind()).get_unique_constraints(
        "connector_installations"
    )
    for constraint in unique_constraints:
        if constraint.get("name") == "uq_connector_installations_project_installation":
            op.drop_constraint(
                constraint["name"], "connector_installations", type_="unique"
            )
