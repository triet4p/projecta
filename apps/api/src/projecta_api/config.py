"""Runtime configuration for the application boundary."""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _projecta_env_file() -> str | None:
    """Load the repository .env when running locally; Compose injects env in containers."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


class Settings(BaseSettings):
    """Configuration injected by Compose or the deployment environment."""

    model_config = SettingsConfigDict(
        env_prefix="PROJECTA_API_",
        env_file=_projecta_env_file(),
        env_ignore_empty=True,
        extra="ignore",
    )

    semantic_core_url: AnyHttpUrl = AnyHttpUrl("http://semantic-core:8080")
    # Empty means the application can still expose liveness, but every
    # project-scoped request must fail closed until deployment configures it.
    trusted_context_secret: str = ""
    # Experience mode starts with no provider profile. Headless and production
    # callers fail closed at operation time through the environment adapter.
    llm_type: Literal["openai-response", "openai"] | None = Field(
        default=None, validation_alias="PROJECTA_LLM_TYPE"
    )
    llm_base_url: AnyHttpUrl | None = Field(default=None, validation_alias="PROJECTA_LLM_BASE_URL")
    llm_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="PROJECTA_LLM_API_KEY")
    llm_model: str = Field(default="", validation_alias="PROJECTA_LLM_MODEL")
    runtime_mode: Literal["headless", "experience", "production"] = "headless"
    operational_database_path: str = ":memory:"
    secret_store_master_key: SecretStr | None = None
    experience_project_id: str = "local-project"
    experience_actor_id: str = "local-user"
