"""Static and executable contracts for Sprint 11 Phase F."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from sprint11_backup import BACKUP_VERSION, create_bundle, restore_bundle


def test_phase_f_scripts_and_compose_boundaries_exist() -> None:
    required = (
        "scripts/check_sprint11_repository_contract.py",
        "scripts/run_sprint11_validation.ps1",
        "scripts/run_sprint11_clean_compose.ps1",
        "scripts/generate_sprint11_acceptance_tls.ps1",
        "scripts/run_sprint11_teams_sandbox.ps1",
        "scripts/run_sprint11_github_public_issues_acceptance.ps1",
        "scripts/run_sprint11_github_public_issues_edit_journey.ps1",
        "scripts/provision_github_public_issues_setup.py",
        "scripts/check_sprint11_github_live_evidence.py",
        "scripts/sprint11_backup.py",
        "scripts/sprint11_cold_recovery.py",
        "scripts/run_sprint11_cold_recovery.ps1",
    )
    for relative in required:
        assert (ROOT / relative).is_file()
    production = (ROOT / "compose.prod.yaml").read_text(encoding="utf-8")
    assert "networks: [private]" in production
    assert "networks: [edge]" in production
    assert "memory: 2G" in production and "memory: 512M" in production
    assert "KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD:?" in production
    assert "aliases: [auth.example.com, projecta.example.com]" in production
    assert "PROJECTA_API_OIDC_CA_FILE" in production
    assert "./infra/edge/tls/auth.crt:/etc/projecta/oidc/ca.crt:ro" in production
    assert "condition: service_started" in production[production.index("  edge:"):production.index("  connector-migrate:")]
    web = production[production.index("  web:"):production.index("\nsecrets:")]
    assert "depends_on: !reset []" in web


def test_clean_compose_runner_bootstraps_and_redacts_operator_material() -> None:
    runner = (ROOT / "scripts/run_sprint11_clean_compose.ps1").read_text(encoding="utf-8")
    for marker in (
        "Initialize OpenBao",
        "Manual unseal share 2",
        "Deterministic identity, secret, Teams, and GitHub journeys",
        "GitHub journeys",
        "Start API, web, and edge after foundations",
        "AppRole re-authentication",
        "operator-sensitive output redacted",
        "Revoke bootstrap root token",
    ):
        assert marker in runner
    assert "<operator-sensitive output redacted>" in runner
    assert '"infra/openbao/tls/tls.crt"' in runner
    assert '"infra/openbao/tls/tls.key"' in runner


def test_acceptance_tls_material_is_short_lived_and_git_ignored() -> None:
    generator = (ROOT / "scripts/generate_sprint11_acceptance_tls.ps1").read_text(encoding="utf-8")
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert '"-days", "7"' in generator
    for marker in ("infra/openbao/tls/", "infra/keycloak/tls/", "infra/edge/tls/"):
        assert marker in ignore


def test_coordinated_bundle_restores_only_into_isolated_target(tmp_path: Path) -> None:
    postgres = tmp_path / "postgres.dump"
    keycloak = tmp_path / "keycloak.json"
    openbao = tmp_path / "openbao.enc"
    evidence = tmp_path / "evidence"
    output = tmp_path / "bundle"
    postgres.write_bytes(b"postgres-state")
    keycloak.write_text(json.dumps({"realm": "projecta"}), encoding="utf-8")
    openbao.write_bytes(b"encrypted-snapshot")
    (evidence / "project").mkdir(parents=True)
    (evidence / "project" / "metadata.json").write_text("{}", encoding="utf-8")
    manifest = create_bundle(output, postgres_dump=postgres, evidence_root=evidence, keycloak_export=keycloak, openbao_snapshot=openbao, confirm_quiesced=True)
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["backupVersion"] == BACKUP_VERSION
    restored = restore_bundle(output, tmp_path / "restored", confirm_isolated=True)
    assert restored.is_file()
    assert (tmp_path / "restored" / "evidence" / "project" / "metadata.json").is_file()
    with pytest.raises(ValueError, match="unsafe"):
        restore_bundle(output, output / "nested", confirm_isolated=True)


def test_cold_recovery_requires_operator_confirmations() -> None:
    script = (ROOT / "scripts/sprint11_cold_recovery.py").read_text(encoding="utf-8")
    for marker in ("manual-unseal-confirmed", "sessions-invalidated", "workload-reauthenticated", "replayMustRemainIdempotent"):
        assert marker in script


def test_stateful_cold_recovery_executes_every_restored_boundary() -> None:
    runner = (ROOT / "scripts/run_sprint11_cold_recovery.ps1").read_text(encoding="utf-8")
    for marker in (
        "Create runtime Keycloak realm export",
        "Create OpenBao Raft snapshot",
        "Destroy complete source state",
        "Restore complete PostgreSQL state",
        "Invalidate all restored Projecta sessions",
        "Verify restored evidence and idempotent replay",
        "original recovery shares",
        "Re-establish workload AppRole authentication",
    ):
        assert marker in runner


def test_phase_f_repository_gate_rejects_paid_and_unbounded_surfaces() -> None:
    gate = (ROOT / "scripts/check_sprint11_repository_contract.py").read_text(encoding="utf-8")
    assert "key vault" in gate.lower()
    assert "max_replies_per_root" in gate
    assert "public connector DTOs stay provider-neutral" in gate


def test_zero_subscription_boundary_is_explicit() -> None:
    docs = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "docs/runbooks/identity-secret-operator-sprint-11.md",
            "docs/runbooks/teams-administrator-sprint-11.md",
            "compose.prod.yaml",
        )
    )
    assert "Azure Key Vault" not in docs
    assert "resource-specific consent" in docs
    assert "non-HA" in docs
