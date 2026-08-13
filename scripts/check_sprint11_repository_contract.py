"""Static repository gates for the Sprint 11 production boundary."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    production = _text("compose.prod.yaml")
    base = _text("compose.yaml")
    public = _text("apps/api/src/projecta_api/connectors/public_api.py")
    browser = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "apps/web/src").rglob("*.ts*"))
    edge = _text("infra/docker/reverse-proxy/nginx.conf")
    github_acceptance = _text("scripts/run_sprint11_github_public_issues_acceptance.ps1")
    github_evidence = json.loads(_text("docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-acceptance.json"))
    github_journey = json.loads(_text("docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-journey.json"))
    g2_packet = _text("docs/sprint-plans/sprint-11/g2-review-packet.md")
    journey_digest = hashlib.sha256(
        (ROOT / "docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-journey.json").read_bytes()
    ).hexdigest()
    complete_journey = (
        github_journey.get("status") == "passed"
        and all(
            key in github_journey.get("editLifecycle", {})
            for key in ("beforeEditRecordDigest", "afterEditRecordDigest")
        )
    )
    waived_journey = (
        github_journey.get("status") == "failed"
        and isinstance(github_journey.get("failure"), str)
        and bool(github_journey.get("failure"))
        and "G2 product/security/release approval: `APPROVED_WITH_RESIDUAL_RISK`" in g2_packet
        and "live edit/replay is explicitly waived" in g2_packet
        and journey_digest in g2_packet
    )
    checks = {
        "production identity is not dev mode": "start-dev" not in production and "start-dev" not in _text("infra/docker/keycloak/Dockerfile"),
        "Keycloak production runtime is prebuilt and immutable": 'command: ["start", "--optimized", "--import-realm"]' in production and "read_only: true" in production,
        "production images are immutable inputs": all(marker in production for marker in ("KEYCLOAK_IMAGE:?", "OPENBAO_IMAGE:?", "API_IMAGE:?", "WEB_IMAGE:?")),
        "OpenBao is private and TLS-backed": "networks: [private]" in production and "BAO_API_ADDR: https://openbao:8200" in production,
        "edge has fixed protocol hosts": "server_name projecta.example.com" in edge and "server_name auth.example.com" in edge,
        "public connector DTOs stay provider-neutral": not any(alias in public for alias in ('alias="tenantId"', 'alias="teamId"', 'alias="channelId"', 'alias="secretReference"')),
        "browser has no secret authority": all(marker not in browser for marker in ("X-Vault-Token", "client_secret", "privateKeyPem", "secret/data/")),
        "no paid managed dependency": not re.search(r"azure|key vault|aws secrets manager|gcp secret manager", production + base + browser, re.IGNORECASE),
        "Teams graph host is fixed": '"graph.microsoft.com"' in _text("apps/api/src/projecta_api/connectors/teams.py") or "graph.microsoft.com" in _text("apps/api/src/projecta_api/connectors/teams.py"),
        "provider traversal remains bounded": "max_replies_per_root" in _text("apps/api/src/projecta_api/connectors/teams.py") and "deadline" in _text("apps/api/src/projecta_api/connectors/orchestration.py"),
        "Teams setup resolver is production composed": "PostgresTeamsSetupRegistry(database)" in _text("apps/api/src/projecta_api/main.py"),
        "OpenBao scripts use the official CLI": "openbao " not in "\n".join(_text(f"scripts/openbao/{name}") for name in ("init.sh", "unseal.sh", "bootstrap-approle.sh", "snapshot.sh", "restore.sh")),
        "GitHub acceptance runner has no provider credential authority": "Authorization =" not in github_acceptance and "[string]$Token" not in github_acceptance and "credentialProvided = $false" in github_acceptance,
        "GitHub live evidence is executable and sanitized": github_evidence.get("schemaVersion") == "sprint11.github-public-issues-live.v2" and github_evidence.get("status") == "passed" and github_evidence.get("generatedBy") == "scripts/run_sprint11_github_public_issues_acceptance.ps1" and github_evidence.get("rawProviderPayload") is False and github_evidence.get("credentialsPersisted") is False and '"verified":' not in json.dumps(github_evidence),
        "GitHub live evidence binds run/snapshot provenance": all(
            key in github_evidence.get("baselineRun", {})
            for key in ("provenanceDigest", "cursorBeforeDigest", "cursorAfterDigest")
        ) and all(
            key in github_evidence.get("providerSnapshot", {})
            for key in ("recordCount", "recordDigest", "snapshotDigest")
        ) and "candidateDeltaCount" in github_evidence.get("continuity", {}),
        "GitHub journey evidence is complete or explicitly waived": github_journey.get("schemaVersion") == "sprint11.github-public-issues-live-journey.v2" and github_journey.get("generatedBy") in {"scripts/run_sprint11_github_public_issues_acceptance.ps1", "scripts/run_sprint11_github_public_issues_edit_journey.ps1"} and github_journey.get("rawProviderPayload") is False and github_journey.get("credentialsPersisted") is False and '"verified":' not in json.dumps(github_journey) and (complete_journey or waived_journey),
    }
    failed = [name for name, passed in checks.items() if not passed]
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
