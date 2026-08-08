"""Bounded provider connection checks with sanitized outcomes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError

from projecta_api.configuration.models import ConnectionCheckResult, LLMConfigurationSnapshot


class ProviderConnectionChecker(Protocol):
    async def check(
        self, snapshot: LLMConfigurationSnapshot, timeout_seconds: float
    ) -> ConnectionCheckResult:
        """Return a bounded, provider-neutral result."""
        ...


class OpenAIConnectionChecker:
    """Use the compatible models endpoint without returning provider payloads."""

    async def check(
        self, snapshot: LLMConfigurationSnapshot, timeout_seconds: float
    ) -> ConnectionCheckResult:
        checked_at = datetime.now(UTC).isoformat()
        client = AsyncOpenAI(
            api_key=snapshot.api_key.get_secret_value(),
            base_url=snapshot.base_url,
            timeout=timeout_seconds,
        )
        try:
            await client.models.list()
        except (APITimeoutError, TimeoutError):
            return ConnectionCheckResult(
                status="unavailable",
                credentialConfigured=True,
                detail="The provider connection timed out.",
                checkedAt=checked_at,
            )
        except (APIConnectionError, APIStatusError, OpenAIError):
            return ConnectionCheckResult(
                status="unhealthy",
                credentialConfigured=True,
                detail="The provider rejected or could not serve the connection check.",
                checkedAt=checked_at,
            )
        finally:
            await client.close()
        return ConnectionCheckResult(
            status="healthy",
            credentialConfigured=True,
            detail="The provider connection is available.",
            checkedAt=checked_at,
        )
