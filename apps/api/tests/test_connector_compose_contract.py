"""Compose topology contract for S10-11 and S10-21."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.local_contract


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_postgres_is_pinned_private_persistent_and_ready_checked() -> None:
    compose = (_repo_root() / "compose.yaml").read_text()
    service = compose.split("  connector-postgres:", 1)[1].split("\n  connector-migrate:", 1)[0]
    assert "postgres:16.4-alpine" in service
    assert "projecta-connector-postgres:/var/lib/postgresql/data" in service
    assert "healthcheck:" in service
    assert "expose:" in service
    assert "ports:" not in service
    assert ":?PROJECTA_CONNECTOR_POSTGRES_PASSWORD" in service


def test_api_migration_and_evidence_are_explicit_dependencies() -> None:
    compose = (_repo_root() / "compose.yaml").read_text()
    api = compose.split("  api:", 1)[1].split("\n  web:", 1)[0]
    assert "connector-migrate:" in api
    assert "service_completed_successfully" in api
    assert "/var/lib/projecta/evidence" in api
    assert "projecta-evidence:/var/lib/projecta/evidence" in api


def test_api_image_prepares_evidence_volume_for_runtime_user() -> None:
    dockerfile = (_repo_root() / "apps" / "api" / "Dockerfile").read_text()
    assert "mkdir -p /var/lib/projecta/evidence" in dockerfile
    assert "chown -R projecta:projecta /var/lib/projecta" in dockerfile


def test_fuseki_runtime_does_not_emit_request_urls() -> None:
    compose = (_repo_root() / "compose.yaml").read_text()
    service = compose.split("  fuseki:", 1)[1].split("\n  fuseki-bootstrap:", 1)[0]
    assert "--quiet" in service
