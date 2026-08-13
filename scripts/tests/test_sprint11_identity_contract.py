"""Repository contracts for the S11 production-shaped identity foundation."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.local_contract


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_keycloak_image_and_production_profile_are_not_dev_mode() -> None:
    dockerfile = (root() / "infra/docker/keycloak/Dockerfile").read_text()
    compose = (root() / "compose.prod.yaml").read_text()
    assert "keycloak/keycloak:26.7.0" in dockerfile
    assert "USER 1000" in dockerfile
    assert '"start-dev"' not in dockerfile + compose
    assert "KEYCLOAK_IMAGE:?" in compose
    assert "memory: 2G" in compose
    assert "KC_HTTP_ENABLED: \"false\"" in compose


def test_keycloak_ownership_isolated_and_repeatable() -> None:
    compose = (root() / "compose.yaml").read_text()
    init = (root() / "infra/postgres/20-keycloak-database.sh").read_text()
    assert "PROJECTA_KEYCLOAK_POSTGRES_USER" in compose
    assert "20-keycloak-database.sh" in compose
    assert "CREATE ROLE" in init and "CREATE DATABASE" not in init
    assert "REVOKE ALL ON DATABASE" in init


def test_realm_template_contains_no_secret_or_bootstrap_authority() -> None:
    realm = (root() / "infra/keycloak/realm.template.json").read_text()
    assert '"clientId": "projecta-web"' in realm
    assert '"pkce.code.challenge.method": "S256"' in realm
    assert '"clientSecret"' not in realm
    assert '"KC_BOOTSTRAP_ADMIN_PASSWORD"' not in realm


def test_edge_routes_only_protocol_surface_and_fixed_hosts() -> None:
    edge = (root() / "infra/docker/reverse-proxy/nginx.conf").read_text()
    assert "server_name projecta.example.com" in edge
    assert "server_name auth.example.com" in edge
    assert "/realms/projecta/.well-known/openid-configuration" in edge
    assert "location / { return 404; }" in edge
    assert "X-Forwarded-Host" in edge


def test_identity_migration_and_runtime_contract_exist() -> None:
    migration = (root() / "apps/api/alembic/versions/0005_identity_sessions_memberships.py").read_text()
    oidc = (root() / "apps/api/src/projecta_api/identity/oidc.py").read_text()
    assert "projecta_sessions" in migration
    assert "projecta_project_memberships" in migration
    assert "projecta_oidc_login_attempts" in migration
    for marker in ("OIDC_ISSUER_INVALID", "OIDC_AUDIENCE_INVALID", "OIDC_SIGNATURE_INVALID", "OIDC_NONCE_INVALID", "code_challenge_method"):
        assert marker in oidc


def test_production_header_stripping_and_browser_cookie_boundary() -> None:
    context = (root() / "apps/api/src/projecta_api/context.py").read_text()
    client = (root() / "apps/web/src/api/client.ts").read_text()
    shell = (root() / "apps/web/src/shell/AuthShell.tsx").read_text()
    assert "x-projecta-context-secret" in context
    assert "runtime_mode == \"production\"" in context
    assert "credentials: \"same-origin\"" in client
    assert "Sign in" in shell and "Sign out" in shell
