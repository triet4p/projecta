"""Runtime configuration for the application boundary."""

from pathlib import Path
from typing import Literal
from urllib.parse import quote

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
        populate_by_name=True,
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
    connector_database_host: str = Field(default="", validation_alias="PROJECTA_CONNECTOR_DATABASE_HOST")
    connector_database_port: int = Field(default=5432, validation_alias="PROJECTA_CONNECTOR_DATABASE_PORT")
    connector_database_name: str = Field(default="", validation_alias="PROJECTA_CONNECTOR_DATABASE_NAME")
    connector_database_user: str = Field(default="", validation_alias="PROJECTA_CONNECTOR_DATABASE_USER")
    connector_database_password: SecretStr = Field(
        default=SecretStr(""), validation_alias="PROJECTA_CONNECTOR_DATABASE_PASSWORD"
    )
    connector_database_url: str | None = Field(
        default=None, validation_alias="PROJECTA_CONNECTOR_DATABASE_URL"
    )
    evidence_root: Path = Field(
        default=Path("/var/lib/projecta/evidence"), validation_alias="PROJECTA_EVIDENCE_ROOT"
    )
    secret_store_master_key: SecretStr | None = None
    experience_actor_id: str | None = None
    # Comma-separated server-owned allowlist. Empty means catalog operations fail closed.
    experience_project_catalog: str = ""
    connector_local_admin_enabled: bool = Field(
        default=False, validation_alias="PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED"
    )

    def connector_sync_database_url(self) -> str:
        """Return the connector DB URL without requiring secrets in Compose URLs."""
        if self.connector_database_url:
            return self.connector_database_url
        if not all(
            (
                self.connector_database_host,
                self.connector_database_name,
                self.connector_database_user,
                self.connector_database_password.get_secret_value(),
            )
        ):
            raise ValueError("connector PostgreSQL configuration is incomplete")
        user = quote(self.connector_database_user, safe="")
        password = quote(self.connector_database_password.get_secret_value(), safe="")
        database = quote(self.connector_database_name, safe="")
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.connector_database_host}:{self.connector_database_port}/{database}"
        )
