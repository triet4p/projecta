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


def test_llm_configuration_is_required(monkeypatch) -> None:
    from pydantic import ValidationError

    for name in ("PROJECTA_LLM_TYPE", "PROJECTA_LLM_BASE_URL", "PROJECTA_LLM_API_KEY", "PROJECTA_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    try:
        Settings(_env_file=None)
    except ValidationError as error:
        assert {item["loc"][0] for item in error.errors()} >= {"PROJECTA_LLM_TYPE", "PROJECTA_LLM_BASE_URL", "PROJECTA_LLM_API_KEY", "PROJECTA_LLM_MODEL"}
    else:
        raise AssertionError("missing LLM configuration must fail closed")
