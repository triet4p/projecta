"""S7-15 through S7-24 persistence, secret, profile, and context contracts."""

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError

from projecta_api.config import Settings
from projecta_api.configuration.audit import ConfigurationAudit
from projecta_api.configuration.errors import ConfigurationProblem, SecretStoreUnavailable
from projecta_api.configuration.models import ConnectionCheckResult, LLMProfileRemove
from projecta_api.configuration.runtime import OperationalRuntimeConfigurationProvider
from projecta_api.configuration.secret_store import ApplicationEncryptedSecretStore
from projecta_api.configuration.service import LLMConfigurationService
from projecta_api.configuration.storage import LLMProfileRepository, OperationalDatabase
from projecta_api.context import TrustedRequestContext
from projecta_api.main import create_app


def test_application_secret_store_encrypts_and_resolves_opaque_references() -> None:
    database = OperationalDatabase(":memory:")
    store = ApplicationEncryptedSecretStore(database, SecretStr(Fernet.generate_key().decode()))

    reference = store.create(SecretStr("do-not-persist-this"))

    assert reference.startswith("secret_")
    assert store.resolve(reference).get_secret_value() == "do-not-persist-this"
    row = database.execute(
        "SELECT ciphertext FROM secret_records WHERE secret_reference = ?", (reference,)
    ).fetchone()
    assert row is not None
    assert b"do-not-persist-this" not in bytes(row["ciphertext"])
    store.delete(reference)
    with pytest.raises(SecretStoreUnavailable):
        store.resolve(reference)


def test_secret_store_fails_closed_when_master_key_is_unavailable() -> None:
    database = OperationalDatabase(":memory:")
    store = ApplicationEncryptedSecretStore(database, None)

    with pytest.raises(SecretStoreUnavailable):
        store.create(SecretStr("credential"))


def test_rotation_and_profile_removal_delete_old_secret() -> None:
    database = OperationalDatabase(":memory:")
    store = ApplicationEncryptedSecretStore(database, SecretStr(Fernet.generate_key().decode()))
    repository = LLMProfileRepository(database)
    first_secret = store.create(SecretStr("first-credential"))
    first = repository.upsert(
        scope="project-1",
        profile_id="profile-1",
        provider_type="openai-response",
        base_url="https://provider.example",
        model="model-1",
        secret_reference=first_secret,
        expected_revision=None,
    )
    second_secret = store.create(SecretStr("second-credential"))
    second = repository.upsert(
        scope="project-1",
        profile_id="profile-1",
        provider_type="openai-response",
        base_url="https://provider.example",
        model="model-2",
        secret_reference=second_secret,
        expected_revision=first.revision,
    )
    old = repository.remove("project-1", second.revision)
    assert old is not None
    store.delete(old.secret_reference)
    store.delete(first_secret)
    with pytest.raises(SecretStoreUnavailable):
        store.resolve(first_secret)
    with pytest.raises(SecretStoreUnavailable):
        store.resolve(second_secret)
    assert repository.get_active("project-1") is None


def test_concurrent_repositories_reject_the_second_stale_revision() -> None:
    database = OperationalDatabase(":memory:")
    store = ApplicationEncryptedSecretStore(database, SecretStr(Fernet.generate_key().decode()))
    repository_a = LLMProfileRepository(database)
    repository_b = LLMProfileRepository(database)
    secret_1 = store.create(SecretStr("secret-1"))
    secret_2 = store.create(SecretStr("secret-2"))
    first = repository_a.upsert(
        scope="project-1",
        profile_id="profile-1",
        provider_type="openai-response",
        base_url="https://provider.example",
        model="model-1",
        secret_reference=secret_1,
        expected_revision=None,
    )
    repository_a.upsert(
        scope="project-1",
        profile_id="profile-1",
        provider_type="openai-response",
        base_url="https://provider.example",
        model="model-2",
        secret_reference=secret_2,
        expected_revision=first.revision,
    )

    with pytest.raises(ConfigurationProblem) as error:
        repository_b.upsert(
            scope="project-1",
            profile_id="profile-1",
            provider_type="openai-response",
            base_url="https://provider.example",
            model="model-stale",
            secret_reference=secret_2,
            expected_revision=first.revision,
        )
    assert error.value.code == "CONFIGURATION_CONFLICT"


def test_dynamic_runtime_provider_returns_a_new_snapshot_after_rotation() -> None:
    database = OperationalDatabase(":memory:")
    store = ApplicationEncryptedSecretStore(database, SecretStr(Fernet.generate_key().decode()))
    repository = LLMProfileRepository(database)
    first_secret = store.create(SecretStr("first-credential"))
    first = repository.upsert(
        scope="project-1",
        profile_id="profile-1",
        provider_type="openai-response",
        base_url="https://provider.example",
        model="model-1",
        secret_reference=first_secret,
        expected_revision=None,
    )
    provider = OperationalRuntimeConfigurationProvider(repository, store)
    context = TrustedRequestContext("project-1", "actor-1", "request-1")
    first_snapshot = provider.resolve_llm(context)

    second_secret = store.create(SecretStr("second-credential"))
    repository.upsert(
        scope="project-1",
        profile_id="profile-1",
        provider_type="openai-response",
        base_url="https://provider.example",
        model="model-2",
        secret_reference=second_secret,
        expected_revision=first.revision,
    )
    second_snapshot = provider.resolve_llm(context)

    assert first_snapshot.revision == "1"
    assert first_snapshot.model == "model-1"
    assert second_snapshot.revision == "2"
    assert second_snapshot.model == "model-2"
    assert second_snapshot.api_key.get_secret_value() == "second-credential"


def test_profile_repository_rejects_stale_revisions() -> None:
    database = OperationalDatabase(":memory:")
    repository = LLMProfileRepository(database)
    database.execute(
        "INSERT INTO secret_records(secret_reference, ciphertext, created_at) VALUES (?, ?, ?)",
        ("secret-1", b"ciphertext", "now"),
    )

    first = repository.upsert(
        scope="project-1",
        profile_id="profile-1",
        provider_type="openai-response",
        base_url="https://provider.example",
        model="model-1",
        secret_reference="secret-1",
        expected_revision=None,
    )

    assert first.revision == 1
    with pytest.raises(ConfigurationProblem) as error:
        repository.upsert(
            scope="project-1",
            profile_id="profile-1",
            provider_type="openai-response",
            base_url="https://provider.example",
            model="model-2",
            secret_reference="secret-2",
            expected_revision=99,
        )
    assert error.value.code == "CONFIGURATION_CONFLICT"


async def test_experience_context_and_settings_boundary_is_server_owned() -> None:
    key = Fernet.generate_key().decode()
    settings = Settings(
        trusted_context_secret="server-context",
        runtime_mode="experience",
        experience_project_id="fixed-project",
        experience_actor_id="fixed-actor",
        secret_store_master_key=key,
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://provider.example",
        PROJECTA_LLM_API_KEY="bootstrap-key",
        PROJECTA_LLM_MODEL="bootstrap-model",
    )
    app = create_app(settings=settings)
    headers = {
        "X-Projecta-Project-Id": "browser-selected-project",
        "X-Projecta-Actor-Id": "browser-selected-actor",
        "X-Projecta-Context-Secret": "browser-secret",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        write = await client.put(
            "/v1/settings/llm",
            headers=headers,
            json={
                "providerType": "openai-response",
                "baseUrl": "https://provider.example",
                "model": "interactive-model",
                "credential": "interactive-secret",
            },
        )
        read = await client.get("/v1/settings/llm", headers=headers)

    assert write.status_code == 200
    assert read.status_code == 200
    assert read.json()["profile"]["model"] == "interactive-model"
    assert read.json()["profile"]["credentialConfigured"] is True
    assert "interactive-secret" not in read.text
    assert read.headers["X-Request-Id"].startswith("experience-")
    snapshot = app.state.runtime_configuration.resolve_llm(
        TrustedRequestContext("fixed-project", "fixed-actor", "request-1")
    )
    assert snapshot.api_key.get_secret_value() == "interactive-secret"


def test_remove_requires_explicit_confirmation() -> None:
    with pytest.raises(ValidationError):
        LLMProfileRemove.model_validate({})


def test_connection_check_health_is_persisted_for_the_checked_revision() -> None:
    database = OperationalDatabase(":memory:")
    store = ApplicationEncryptedSecretStore(database, SecretStr(Fernet.generate_key().decode()))
    repository = LLMProfileRepository(database)
    audit = ConfigurationAudit(database)
    service = LLMConfigurationService(repository, store, audit, runtime_mode="experience")
    secret = store.create(SecretStr("credential"))
    profile = repository.upsert(
        scope="project-1",
        profile_id="profile-1",
        provider_type="openai-response",
        base_url="https://provider.example",
        model="model-1",
        secret_reference=secret,
        expected_revision=None,
    )

    service.record_connection_check(
        TrustedRequestContext("project-1", "actor-1", "request-1"),
        str(profile.revision),
        ConnectionCheckResult(
            status="unhealthy",
            credentialConfigured=True,
            detail="sanitized",
            checkedAt="2026-08-06T00:00:00Z",
        ),
    )

    stored = repository.get_active("project-1")
    assert stored is not None
    assert stored.health == "unhealthy"
    assert stored.last_checked_at == "2026-08-06T00:00:00Z"
