from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from cryptography.fernet import Fernet

pytestmark = pytest.mark.local_contract


@pytest.fixture
def native_launcher() -> tuple[ModuleType, Path]:
    repository_root = Path(__file__).resolve().parents[3]
    launcher_path = repository_root / "scripts" / "projecta_local.py"
    launcher_spec = importlib.util.spec_from_file_location("native_opt_in_launcher", launcher_path)
    if launcher_spec is None or launcher_spec.loader is None:
        raise RuntimeError("could not load the native launcher")
    launcher = importlib.util.module_from_spec(launcher_spec)
    sys.modules[launcher_spec.name] = launcher
    launcher_spec.loader.exec_module(launcher)
    return launcher, repository_root


_FOREIGN_ENVIRONMENT = {
    "PROJECTA_API_TRUSTED_CONTEXT_SECRET": "foreign-context-secret",
    "PROJECTA_API_RUNTIME_MODE": "production",
    "PROJECTA_API_EXPERIENCE_ACTOR_ID": "foreign-actor",
    "PROJECTA_API_EXPERIENCE_PROJECT_CATALOG": "foreign-project",
    "PROJECTA_API_SECRET_STORE_MASTER_KEY": "not-a-fernet-key",
    "PROJECTA_CONNECTOR_DATABASE_PASSWORD": "foreign-database-password",
    "PROJECTA_CONNECTOR_DATABASE_URL": "postgresql://foreign.invalid/projecta",
    "PROJECTA_API_OIDC_CLIENT_ID": "foreign-oidc-client",
    "PROJECTA_API_OPENBAO_URL": "https://foreign-secret-service.invalid",
    "PROJECTA_LLM_API_KEY": "foreign-provider-key",
    "PROJECTA_UNRELATED_TRUST_ANCHOR": "foreign-trust-anchor",
    "OPENAI_API_KEY": "foreign-provider-key",
    "ANTHROPIC_API_KEY": "foreign-provider-key",
    "AWS_SECRET_ACCESS_KEY": "foreign-cloud-secret",
    "GOOGLE_APPLICATION_CREDENTIALS": "foreign-cloud-credentials",
    "FUSEKI_TOKEN": "foreign-fuseki-token",
    "SEMANTIC_CORE_TRUST_TOKEN": "foreign-core-token",
    "PGPASSWORD": "foreign-database-password",
    "PGUSER": "foreign-database-user",
    "PGHOST": "foreign.invalid",
    "PGPORT": "15432",
    "PGDATABASE": "foreign-database",
    "HTTPS_PROXY": "http://127.0.0.1:9",
    "HTTP_PROXY": "http://127.0.0.1:9",
    "ALL_PROXY": "http://127.0.0.1:9",
    "NO_PROXY": "example.invalid",
    "JAVA_TOOL_OPTIONS": "-Dprojecta.foreign=true",
    "JDK_JAVA_OPTIONS": "-Dprojecta.foreign=true",
    "CLASSPATH": "foreign.classpath",
}

_CHILD_SCENARIO = r'''
import json
import os
import sys
from datetime import UTC, datetime

from pydantic import ValidationError

payload = json.loads(sys.argv[1])
expected = payload["settings"]
sys.path.insert(0, payload["api_source"])

from fastapi.testclient import TestClient
from projecta_api.config import Settings
from projecta_api.connectors.authorization import ConnectorPolicy, LocalConnectorPrincipalAdapter
from projecta_api.connectors.installation_service import ConnectorInstallationService
from projecta_api.connectors.json_mock import JsonMockAdapter, JsonMockFixture
from projecta_api.connectors.public_api import ConnectorRuntime
from projecta_api.connectors.registry import ConnectorRegistry
from projecta_api.operational.ports import InstallationRecord
from projecta_api.project_workspace import catalog_revision, opaque_project_handle

try:
    # The installed native package has no repo-local .env.
    settings = Settings(_env_file=None)
except ValidationError:
    print(json.dumps({"result": "invalid-settings"}))
    raise SystemExit(0)

from projecta_api.main import create_app

assert settings.runtime_mode == "experience"
assert settings.trusted_context_secret == expected["trusted_context_secret"]
assert settings.experience_actor_id == expected["actor_id"]
assert settings.experience_project_catalog == expected["project_id"]
assert settings.secret_store_master_key.get_secret_value() == expected["secret_store_master_key"]
assert settings.connector_database_password.get_secret_value() == expected["database_password"]
assert settings.llm_api_key.get_secret_value() == ""
for name in (
    "PROJECTA_API_OIDC_CLIENT_ID",
    "PROJECTA_API_OPENBAO_URL",
    "PROJECTA_CONNECTOR_DATABASE_URL",
    "PROJECTA_UNRELATED_TRUST_ANCHOR",
    "PROJECTA_LLM_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "FUSEKI_TOKEN",
    "SEMANTIC_CORE_TRUST_TOKEN",
    "PGPASSWORD",
    "PGUSER",
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "JAVA_TOOL_OPTIONS",
    "JDK_JAVA_OPTIONS",
    "CLASSPATH",
):
    assert name not in os.environ, name

class Repository:
    def __init__(self):
        self.installations = {}

    def get_installation(self, project_id, installation_id):
        return self.installations.get((project_id, installation_id))

    def list_installations(self, project_id, *, limit=50, offset=0):
        records = [record for (scope, _), record in self.installations.items() if scope == project_id]
        return records[offset : offset + limit]

    def upsert_installation(
        self,
        *,
        project_id,
        installation_id,
        connector_type,
        capability_snapshot,
        secret_reference,
        enabled,
        expected_revision,
        audit_operation=None,
        actor_reference=None,
        correlation_id=None,
    ):
        now = datetime.now(UTC)
        record = InstallationRecord(
            installation_id=installation_id,
            project_id=project_id,
            connector_type=connector_type,
            capability_snapshot=capability_snapshot,
            secret_reference=secret_reference,
            enabled=enabled,
            revision=1,
            created_at=now,
            updated_at=now,
        )
        self.installations[(project_id, installation_id)] = record
        return record

repository = Repository()
principal = LocalConnectorPrincipalAdapter(settings)
policy = ConnectorPolicy(principal, repository, repository)
registry = ConnectorRegistry()
registry.register(
    JsonMockAdapter(
        JsonMockFixture.model_validate(
            {
                "fixtureVersion": "json-mock.v1",
                "connectorType": "json-mock",
                "resources": [
                    {
                        "externalReference": "fixture://native-local/message-001",
                        "occurredAt": "2026-10-09T00:00:00Z",
                        "eventType": "source.created",
                        "contentType": "application/json",
                        "content": {"title": "Local connector test"},
                    }
                ],
            }
        )
    )
)
installation_service = ConnectorInstallationService(repository, policy, registry)
runtime = ConnectorRuntime(
    repository,
    registry,
    installation_service,
    None,
    policy,
    None,
    None,
)
app = create_app(settings=settings, connector_runtime=runtime)
project_id = expected["project_id"]
project_handle = opaque_project_handle(project_id)
app.state.project_selection_repository.replace(
    expected["actor_id"],
    project_handle,
    project_id,
    catalog_revision((project_id,)),
)
client = TestClient(app)
response = client.post(
    f"/v1/projects/{project_handle}/connectors/installations",
    json={
        "connectorType": "json-mock",
        "fixtureReference": "fixture://native-local",
    },
)
result = {
    "status": response.status_code,
    "code": response.json().get("code"),
    "stored_installations": len(repository.installations),
}
client.close()
print(json.dumps(result))
'''


@pytest.mark.parametrize(
    ("opt_in", "expected_result"),
    [
        pytest.param(None, {"status": 403, "code": "CONNECTOR_FORBIDDEN", "stored_installations": 0}, id="absent"),
        pytest.param("", {"status": 403, "code": "CONNECTOR_FORBIDDEN", "stored_installations": 0}, id="empty"),
        pytest.param("false", {"status": 403, "code": "CONNECTOR_FORBIDDEN", "stored_installations": 0}, id="false"),
        pytest.param("0", {"status": 403, "code": "CONNECTOR_FORBIDDEN", "stored_installations": 0}, id="zero"),
        pytest.param("off", {"status": 403, "code": "CONNECTOR_FORBIDDEN", "stored_installations": 0}, id="off"),
        pytest.param("true", {"status": 201, "code": None, "stored_installations": 1}, id="true"),
        pytest.param("yes", {"status": 201, "code": None, "stored_installations": 1}, id="yes"),
        pytest.param("1", {"status": 201, "code": None, "stored_installations": 1}, id="one"),
        pytest.param("malformed", {"result": "invalid-settings"}, id="malformed"),
    ],
)
def test_native_opt_in_controls_real_connector_install_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_launcher: tuple[ModuleType, Path],
    opt_in: str | None,
    expected_result: dict[str, object],
) -> None:
    for name, value in _FOREIGN_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    if opt_in is None:
        monkeypatch.delenv("PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED", raising=False)
    else:
        monkeypatch.setenv("PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED", opt_in)

    project_id = "native-local"
    actor_id = "local-operator"
    trusted_context_secret = "native-test-context-secret"
    database_password = "native-test-database-password"
    secret_store_master_key = Fernet.generate_key().decode("ascii")
    launcher, repository_root = native_launcher
    paths = launcher.ProjectaPaths(tmp_path / "package", tmp_path / "user-data")
    paths.ensure_user_directories()
    (paths.project / "web").mkdir(parents=True)
    (paths.project / "web" / "index.html").write_text("<main>test</main>", encoding="utf-8")
    paths.local_config.write_text(
        json.dumps(
            {
                "formatVersion": 1,
                "projectId": project_id,
                "projectName": "Native Local",
                "actorId": actor_id,
                "projects": [{"projectId": project_id, "projectName": "Native Local"}],
            }
        ),
        encoding="utf-8",
    )
    manager = launcher.RuntimeManager(paths, open_browser=False)
    manager.workspace = launcher.WorkspaceConfig(project_id, "Native Local", actor_id)
    manager.secrets = launcher.RuntimeSecrets(
        database_password,
        trusted_context_secret,
        secret_store_master_key,
    )
    # `_start_api()` calls `_api_environment()` with no explicit base.

    environment = manager._api_environment()

    payload = {
        "api_source": str(repository_root / "apps" / "api" / "src"),
        "settings": {
            "project_id": project_id,
            "actor_id": actor_id,
            "trusted_context_secret": trusted_context_secret,
            "database_password": database_password,
            "secret_store_master_key": secret_store_master_key,
        },
    }
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_SCENARIO, json.dumps(payload)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == expected_result
