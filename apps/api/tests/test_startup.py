from projecta_api.config import Settings
from projecta_api.startup import validate_startup


def test_experience_requires_explicit_scope_and_secret_store() -> None:
    problems = validate_startup(
        Settings(
            _env_file=None,
            runtime_mode="experience",
            trusted_context_secret="context",
        )
    )

    assert [problem.code for problem in problems] == [
        "EXPERIENCE_PROJECT_CATALOG_MISSING",
        "EXPERIENCE_ACTOR_CONFIGURATION_MISSING",
        "SECRET_STORE_CONFIGURATION_MISSING",
    ]


def test_experience_accepts_an_explicit_empty_catalog() -> None:
    problems = validate_startup(
        Settings(
            _env_file=None,
            runtime_mode="experience",
            trusted_context_secret="context",
            experience_project_catalog="[]",
            experience_actor_id="actor-1",
            secret_store_master_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        )
    )

    assert problems == ()


def test_valid_headless_configuration_has_no_startup_problems() -> None:
    problems = validate_startup(
        Settings(
            _env_file=None,
            trusted_context_secret="context",
            PROJECTA_LLM_TYPE="openai-response",
            PROJECTA_LLM_BASE_URL="https://provider.example",
            PROJECTA_LLM_API_KEY="test-key",
            PROJECTA_LLM_MODEL="test-model",
        )
    )

    assert problems == ()
