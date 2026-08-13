"""Seeded-secret leak gate for the OpenBao boundary."""

from pathlib import Path


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def _text_files() -> list[Path]:
    base = root()
    suffixes = {
        ".env", ".json", ".log", ".md", ".py", ".sh", ".sql", ".ts", ".tsx",
        ".ttl", ".yaml", ".yml",
    }
    gate = Path(__file__).resolve()
    files: list[Path] = []
    for directory in ("apps", "docs", "evaluation", "infra", "ontology", "scripts"):
        target = base / directory
        if target.is_dir():
            files.extend(
                path
                for path in target.rglob("*")
                if path.is_file()
                and path.suffix.lower() in suffixes
                and path.resolve() != gate
                and ".venv" not in path.parts
                and "__pycache__" not in path.parts
            )
    files.extend(base / name for name in (".env.example", "compose.yaml", "compose.prod.yaml"))
    return files


def test_seeded_runtime_material_is_absent_from_public_and_recovery_artifacts() -> None:
    seeded = {
        "seeded-production-secret",
        "openbao-root-token-seeded",
        "projecta-secret-id-seeded",
        "seeded-provider-access-token",
    }
    for path in _text_files():
        content = path.read_text(encoding="utf-8")
        assert not seeded.intersection(content), f"seeded secret leaked into {path}"


def test_forbidden_secret_surfaces_are_not_browser_or_public_contracts() -> None:
    base = root()
    browser = "\n".join(path.read_text(encoding="utf-8") for path in base.joinpath("apps/web/src").rglob("*.*"))
    public_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            base / "apps/api/src/projecta_api/connectors/public_api.py",
            base / "apps/api/src/projecta_api/identity/routes.py",
            base / "apps/api/src/projecta_api/routes.py",
        )
    )
    assert "X-Vault-Token" not in browser
    assert "SecretID" not in browser
    assert "openbao-root-token" not in browser
    assert "client_token" not in public_source
    assert "seeded-production-secret" not in public_source
    assert "secret/data/projecta/connector/v1" not in public_source


def test_compose_uses_restricted_secret_files_without_inline_tokens() -> None:
    base = root()
    production = (base / "compose.prod.yaml").read_text(encoding="utf-8")
    assert "openbao-role-id:" in production
    assert "openbao-secret-id:" in production
    assert "BAO_TOKEN:" not in production
    assert "secret_id:" not in production
