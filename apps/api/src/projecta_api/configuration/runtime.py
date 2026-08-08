"""Operation-time resolution of the approved interactive profile."""

from __future__ import annotations

from projecta_api.configuration.errors import SecretStoreUnavailable
from projecta_api.configuration.models import LLMConfigurationSnapshot
from projecta_api.configuration.ports import RuntimeConfigurationProvider, SecretStore
from projecta_api.configuration.storage import LLMProfileRepository
from projecta_api.context import TrustedRequestContext
from projecta_api.llm.gateway import NormalizedGatewayError


class OperationalRuntimeConfigurationProvider:
    """Resolve a project-scoped profile and secret for one operation."""

    def __init__(self, repository: LLMProfileRepository, secret_store: SecretStore) -> None:
        self._repository = repository
        self._secret_store = secret_store

    def resolve_llm(self, context: TrustedRequestContext | None = None) -> LLMConfigurationSnapshot:
        if context is None:
            raise NormalizedGatewayError(
                "configuration_invalid", "project context is required", retryable=False
            )
        profile = self._repository.get_active(context.project_id)
        if profile is None or not profile.secret_reference:
            raise NormalizedGatewayError(
                "configuration_invalid", "interactive LLM profile is not configured", retryable=False
            )
        try:
            api_key = self._secret_store.resolve(profile.secret_reference)
        except SecretStoreUnavailable as error:
            raise NormalizedGatewayError(
                "configuration_invalid", "interactive secret store is unavailable", retryable=True
            ) from error
        if not api_key.get_secret_value():
            raise NormalizedGatewayError(
                "configuration_invalid", "interactive credential is unavailable", retryable=False
            )
        return LLMConfigurationSnapshot(
            provider_type=profile.provider_type,  # type: ignore[arg-type]
            base_url=profile.base_url,
            model=profile.model,
            api_key=api_key,
            revision=str(profile.revision),
        )


def resolve_for_context(
    provider: RuntimeConfigurationProvider, context: TrustedRequestContext
) -> LLMConfigurationSnapshot:
    """Call both legacy environment and dynamic providers uniformly."""
    return provider.resolve_llm(context)
