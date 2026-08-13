"""Repository contracts for the S11 OpenBao production-shaped boundary."""

from pathlib import Path


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_openbao_image_storage_tls_and_resource_contract() -> None:
    dockerfile = (root() / "infra/docker/openbao/Dockerfile").read_text()
    config = (root() / "infra/openbao/config.hcl").read_text()
    compose = (root() / "compose.yaml").read_text()
    production = (root() / "compose.prod.yaml").read_text()
    assert "ghcr.io/openbao/openbao:2.6.1" in dockerfile
    assert "USER 100" in dockerfile
    assert 'storage "raft"' in config
    assert 'api_addr = "https://openbao:8200"' in config
    assert "tls_min_version = \"tls13\"" in config
    assert 'profiles: ["secrets"]' in compose
    assert "ports:" not in compose[compose.index("  openbao:"):compose.index("  connector-migrate:")]
    assert "OPENBAO_IMAGE:?OPENBAO_IMAGE must be an immutable 2.6.1 digest reference" in production
    assert 'cpus: "0.5"' in production and "memory: 512M" in production


def test_operator_and_workload_bootstrap_contract_is_fail_closed() -> None:
    init = (root() / "scripts/openbao/init.sh").read_text()
    unseal = (root() / "scripts/openbao/unseal.sh").read_text()
    bootstrap = (root() / "scripts/openbao/bootstrap-approle.sh").read_text()
    policy = (root() / "infra/openbao/policies/projecta-api.hcl").read_text()
    for marker in ("key-shares=3", "key-threshold=2", "jq", "already initialized", "not printed"):
        assert marker in init
    assert '"$(cat "$file")"' in unseal
    for marker in ("token_ttl=15m", "token_max_ttl=60m", "secret_id_ttl=10m", "secret_id_num_uses=1", "token revoke", "unset BAO_TOKEN"):
        assert marker in bootstrap
    assert "auth/approle/role/projecta-api/role-id" in bootstrap
    assert 'path "secret/data/projecta/connector/v1/*"' in policy
    assert 'capabilities = ["create", "read", "update", "delete"]' in policy
    assert 'capabilities = ["list"]' not in policy
    for forbidden in ("sys/policies", "sys/seal", 'path "secret/*"'):
        assert forbidden not in policy


def test_every_operator_script_uses_the_official_bao_executable() -> None:
    for name in ("init.sh", "unseal.sh", "bootstrap-approle.sh", "snapshot.sh", "restore.sh"):
        script = (root() / "scripts/openbao" / name).read_text()
        executable_lines = [
            line.strip()
            for line in script.splitlines()
            if line.strip().startswith(("bao ", "openbao "))
        ]
        assert executable_lines, f"{name} has no OpenBao CLI invocation"
        assert all(line.startswith("bao ") for line in executable_lines), name


def test_initialization_reads_the_openbao_json_unseal_key_field() -> None:
    init = (root() / "scripts/openbao/init.sh").read_text()
    runner = (root() / "scripts/run_sprint11_clean_compose.ps1").read_text()
    assert ".unseal_keys_b64[0]" in init
    assert "$init.unseal_keys_b64" in runner
    assert "keys_base64" not in init
    assert "keys_base64" not in runner


def test_versioned_adapter_and_recovery_contract_are_present() -> None:
    ports = (root() / "apps/api/src/projecta_api/configuration/ports.py").read_text()
    adapter = (root() / "apps/api/src/projecta_api/secrets/openbao.py").read_text()
    restore = (root() / "scripts/openbao/restore.sh").read_text()
    assert "class SecretScope" in ports and "class VersionedSecretStore" in ports
    for marker in ("create_scoped", "resolve_scoped", "rotate_scoped", "revoke_scoped", "SCOPE_REQUIRED", "cache_ttl_seconds"):
        assert marker in adapter
    for marker in ("openssl enc", "sha256sum -c", "contract version mismatch", "manual unseal"):
        assert marker in restore


def test_production_composition_requires_openbao_for_connector_runtime() -> None:
    main = (root() / "apps/api/src/projecta_api/main.py").read_text()
    secrets = (root() / "apps/api/src/projecta_api/connectors/secrets.py").read_text()
    assert "not isinstance(secret_store, OpenBaoSecretStore)" in main
    assert "SECRET_MANAGER_UNAVAILABLE" in main
    assert "installation.revision" in secrets
    assert "providerTenant" in secrets
    assert "SECRET_SEALED" in secrets and "SECRET_REVOKED" in secrets
