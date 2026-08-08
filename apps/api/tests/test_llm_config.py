"""Provider configuration must fail closed at the live-adapter boundary."""

from projecta_api.config import Settings


def test_llm_configuration_is_explicit_and_secret_is_redacted() -> None:
    settings = Settings(
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://api.deepseek.com",
        PROJECTA_LLM_API_KEY="secret-value",
        PROJECTA_LLM_MODEL="deepseek-v4-flash",
    )

    assert settings.llm_type == "openai-response"
    assert str(settings.llm_base_url) == "https://api.deepseek.com/"
    assert settings.llm_model == "deepseek-v4-flash"
    assert "secret-value" not in repr(settings)


def test_llm_configuration_can_be_absent_before_first_run(monkeypatch) -> None:
    for name in ("PROJECTA_LLM_TYPE", "PROJECTA_LLM_BASE_URL", "PROJECTA_LLM_API_KEY", "PROJECTA_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)

    assert settings.llm_type is None
    assert settings.llm_base_url is None
    assert settings.llm_api_key.get_secret_value() == ""
    assert settings.llm_model == ""
