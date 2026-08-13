"""Contract tests for the PostgreSQL operational boundary and migration runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from projecta_api.operational.schema import Base

pytestmark = pytest.mark.local_contract


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_connector_schema_has_project_scoped_tables_and_no_raw_payload_columns() -> None:
    expected = {
        "connector_installations",
        "connector_event_inbox",
        "connector_sync_runs",
        "connector_sync_attempts",
        "connector_cursors",
        "connector_dead_letters",
            "connector_audit_records",
            "teams_setup_handles",
            "github_public_issues_setup_handles",
    }
    assert expected == set(Base.metadata.tables)
    for table in Base.metadata.tables.values():
        assert "project_id" in table.columns or table.name == "connector_sync_attempts"
        assert "raw_payload" not in table.columns
        assert "secret" not in {column.name for column in table.columns if column.name != "secret_reference"}


def test_migration_is_forward_only_at_the_application_entrypoint() -> None:
    root = _repo_root()
    runner = (root / "apps" / "api" / "src" / "projecta_api" / "operational" / "migrate.py").read_text()
    assert 'choices=("upgrade",)' in runner
    assert "command.upgrade" in runner
    assert "downgrade" in runner
    env = (root / "apps" / "api" / "alembic" / "env.py").read_text()
    assert "pg_advisory_lock" in env
