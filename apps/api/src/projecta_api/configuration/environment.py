"""Headless/deployment environment adapter for runtime configuration."""

from projecta_api.config import Settings
from projecta_api.configuration.models import LLMConfigurationSnapshot
from projecta_api.context import TrustedRequestContext
from projecta_api.llm.gateway import NormalizedGatewayError


class EnvironmentRuntimeConfigurationProvider:
    """Adapt the explicit PROJECTA_LLM_* bootstrap contract to the port."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve_llm(
        self, context: TrustedRequestContext | None = None
    ) -> LLMConfigurationSnapshot:
        """Resolve the current environment profile without exposing raw config."""
        del context
        if (
            self._settings.llm_type is None
            or self._settings.llm_base_url is None
            or not self._settings.llm_model.strip()
            or not self._settings.llm_api_key.get_secret_value()
        ):
            raise NormalizedGatewayError(
                "configuration_invalid",
                "live provider configuration is not configured",
                retryable=False,
            )
        return LLMConfigurationSnapshot(
            provider_type=self._settings.llm_type,
            base_url=str(self._settings.llm_base_url),
            model=self._settings.llm_model,
            api_key=self._settings.llm_api_key,
            revision="environment",
        )
