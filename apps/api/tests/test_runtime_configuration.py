"""S7-10 through S7-12 configuration-port and redaction contracts."""

from projecta_api.config import Settings
from projecta_api.configuration.environment import EnvironmentRuntimeConfigurationProvider
from projecta_api.configuration.models import LLMProfile
from projecta_api.llm.gateway import NormalizedGatewayError


def _settings(provider_type: str) -> Settings:
    return Settings(
        PROJECTA_LLM_TYPE=provider_type,
        PROJECTA_LLM_BASE_URL="https://api.deepseek.com",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="deepseek-v4-flash",
    )


def test_environment_adapter_preserves_both_supported_provider_types() -> None:
    for provider_type in ("openai-response", "openai"):
        snapshot = EnvironmentRuntimeConfigurationProvider(_settings(provider_type)).resolve_llm()

        assert snapshot.provider_type == provider_type
        assert snapshot.base_url == "https://api.deepseek.com/"
        assert snapshot.model == "deepseek-v4-flash"
        assert snapshot.api_key.get_secret_value() == "test-key"
        assert snapshot.revision == "environment"


def test_profile_serialization_excludes_secret_reference_and_raw_secret() -> None:
    profile = LLMProfile(
        profileId="profile-1",
        providerType="openai-response",
        baseUrl="https://api.deepseek.com",
        model="deepseek-v4-flash",
        revision=3,
        credentialConfigured=True,
        secretReference="secret-ref-internal",
    )

    serialized = profile.model_dump(mode="json", by_alias=True)
    assert "secretReference" not in serialized
    assert "test-key" not in repr(profile)
    assert serialized["credentialConfigured"] is True


def test_snapshot_redacted_profile_contains_status_only() -> None:
    snapshot = EnvironmentRuntimeConfigurationProvider(_settings("openai-response")).resolve_llm()

    redacted = snapshot.redacted_profile().model_dump(mode="json", by_alias=True)
    assert redacted["credentialConfigured"] is True
    assert "apiKey" not in redacted
    assert "secretReference" not in redacted
    assert "test-key" not in str(redacted)


def test_environment_adapter_fails_closed_when_first_run_has_no_llm_bootstrap(monkeypatch) -> None:
    for name in ("PROJECTA_LLM_TYPE", "PROJECTA_LLM_BASE_URL", "PROJECTA_LLM_API_KEY", "PROJECTA_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)

    try:
        EnvironmentRuntimeConfigurationProvider(settings).resolve_llm()
    except NormalizedGatewayError as error:
        assert error.error_class == "configuration_invalid"
    else:
        raise AssertionError("missing headless bootstrap must fail closed")
