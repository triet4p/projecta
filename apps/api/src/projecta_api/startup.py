"""Fail-closed startup/readiness validation for deployment-owned configuration."""

from dataclasses import dataclass
from urllib.parse import urlparse

from cryptography.fernet import Fernet

from projecta_api.config import Settings
from projecta_api.project_workspace import configured_project_ids


@dataclass(frozen=True, slots=True)
class StartupProblem:
    """Safe readiness diagnostic; never contains raw configuration values."""

    code: str


def validate_startup(settings: Settings) -> tuple[StartupProblem, ...]:
    """Return finite configuration problems without performing network I/O."""

    problems: list[StartupProblem] = []
    if settings.web_assets_directory is not None:
        web_index = settings.web_assets_directory / "index.html"
        if not settings.web_assets_directory.is_dir() or not web_index.is_file():
            problems.append(StartupProblem("WEB_ASSETS_CONFIGURATION_INVALID"))
    if not str(settings.semantic_core_url).strip():
        problems.append(StartupProblem("SEMANTIC_CORE_CONFIGURATION_INVALID"))
    parsed = urlparse(str(settings.semantic_core_url))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        problems.append(StartupProblem("SEMANTIC_CORE_CONFIGURATION_INVALID"))

    if settings.runtime_mode != "production" and not settings.trusted_context_secret.strip():
        problems.append(StartupProblem("TRUSTED_CONTEXT_CONFIGURATION_MISSING"))

    if settings.runtime_mode == "experience":
        if not settings.experience_project_catalog.strip():
            problems.append(StartupProblem("EXPERIENCE_PROJECT_CATALOG_MISSING"))
        else:
            try:
                configured_project_ids(settings.experience_project_catalog)
            except ValueError:
                problems.append(StartupProblem("EXPERIENCE_PROJECT_CATALOG_INVALID"))
        if not settings.experience_actor_id or not settings.experience_actor_id.strip():
            problems.append(StartupProblem("EXPERIENCE_ACTOR_CONFIGURATION_MISSING"))
        master_key = settings.secret_store_master_key.get_secret_value() if settings.secret_store_master_key else ""
        if not master_key:
            problems.append(StartupProblem("SECRET_STORE_CONFIGURATION_MISSING"))
        else:
            try:
                Fernet(master_key.encode("ascii"))
            except (ValueError, UnicodeEncodeError):
                problems.append(StartupProblem("SECRET_STORE_CONFIGURATION_INVALID"))
    elif settings.runtime_mode == "production":
        # Production context and provider ownership are deployment concerns;
        # the local experience adapter must not be silently selected.
        if settings.experience_actor_id or settings.experience_project_catalog:
            problems.append(StartupProblem("EXPERIENCE_CONTEXT_DISABLED_IN_PRODUCTION"))
        if settings.connector_local_admin_enabled:
            problems.append(StartupProblem("CONNECTOR_LOCAL_AUTH_DISABLED_IN_PRODUCTION"))
        if not settings.oidc_issuer_url or not settings.oidc_client_id.strip() or not settings.oidc_redirect_uri or not settings.oidc_audience.strip():
            problems.append(StartupProblem("OIDC_CONFIGURATION_MISSING"))
        if not settings.identity_database_url and not all(
            (settings.connector_database_host, settings.connector_database_name,
             settings.connector_database_user, settings.connector_database_password.get_secret_value())
        ):
            problems.append(StartupProblem("IDENTITY_DATABASE_CONFIGURATION_MISSING"))
        if not settings.openbao_url:
            problems.append(StartupProblem("OPENBAO_CONFIGURATION_MISSING"))
    elif not _provider_configuration_is_complete(settings):
        problems.append(StartupProblem("LLM_CONFIGURATION_MISSING"))

    return tuple(dict.fromkeys(problems))


def _provider_configuration_is_complete(settings: Settings) -> bool:
    """Check presence only; provider adapters perform their own policy checks."""

    return bool(
        settings.llm_type
        and settings.llm_base_url
        and settings.llm_model.strip()
        and settings.llm_api_key.get_secret_value()
    )
