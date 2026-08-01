"""Runtime configuration for the application boundary."""

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration injected by Compose or the deployment environment."""

    model_config = SettingsConfigDict(env_prefix="PROJECTA_API_", extra="ignore")

    semantic_core_url: AnyHttpUrl = AnyHttpUrl("http://semantic-core:8080")
    # Empty means the application can still expose liveness, but every
    # project-scoped request must fail closed until deployment configures it.
    trusted_context_secret: str = ""
