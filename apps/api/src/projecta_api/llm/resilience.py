"""Bounded retry policy for normalized provider gateway failures."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Literal

from projecta_api.llm.gateway import (
    GatewayRequest,
    GatewayResponse,
    LLMGateway,
    NormalizedGatewayError,
)
from projecta_api.llm.telemetry import ProviderAttemptEvent, emit_provider_attempt_event

RetryMode = Literal[
    "interactive-single-attempt",
    "explicit-user-retry",
    "offline-replay",
    "live-quality-evaluation",
    "health-probe",
    "operator-recovery",
]

_BOUNDED_RETRY_CLASSES = {"timeout", "rate_limit", "provider_failure"}


class ResilientGateway:
    """Apply a declared retry mode; interactive extraction is single-attempt."""

    def __init__(
        self,
        gateway: LLMGateway,
        *,
        mode: RetryMode = "interactive-single-attempt",
        max_retries: int = 0,
        base_delay_seconds: float = 0.05,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        provider: str = "provider-adapter",
        logger: logging.Logger | None = None,
    ) -> None:
        if not 0 <= max_retries <= 3:
            raise ValueError("max_retries must be between 0 and 3")
        if not 0 <= base_delay_seconds <= 2:
            raise ValueError("base_delay_seconds must be between 0 and 2")
        self._gateway = gateway
        self._mode = mode
        self._max_retries = max_retries
        self._base_delay_seconds = base_delay_seconds
        self._sleeper = sleeper
        self._provider = provider
        self._logger = logger or logging.getLogger("projecta.provider")

    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        """Execute the bounded attempts authorized by the selected mode."""
        attempts = self._attempt_budget()
        for attempt in range(attempts):
            started = monotonic()
            emit_provider_attempt_event(
                self._logger,
                ProviderAttemptEvent(
                    event="provider.attempt.started",
                    schemaVersion="s8.logging.v1",
                    requestId=request.request_id,
                    operationId=request.operation_id,
                    provider=self._provider,
                    attempt=attempt + 1,
                    configuredTimeoutMs=int(request.timeout_seconds * 1000),
                    modelVersion=request.model_id,
                    profileRevision=request.profile_revision,
                ),
            )
            try:
                result = await self._gateway.extract(request)
                usage = result.usage
                emit_provider_attempt_event(
                    self._logger,
                    ProviderAttemptEvent(
                        event="provider.attempt.completed",
                        schemaVersion="s8.logging.v1",
                        requestId=request.request_id,
                        operationId=request.operation_id,
                        provider=self._provider,
                        attempt=attempt + 1,
                        configuredTimeoutMs=int(request.timeout_seconds * 1000),
                        modelVersion=request.model_id,
                        profileRevision=request.profile_revision,
                        latencyMs=int((monotonic() - started) * 1000),
                        terminalOutcome="success",
                        inputTokens=usage.input_tokens if usage else None,
                        outputTokens=usage.output_tokens if usage else None,
                    ),
                )
                return result
            except NormalizedGatewayError as error:
                emit_provider_attempt_event(
                    self._logger,
                    ProviderAttemptEvent(
                        event="provider.attempt.completed",
                        schemaVersion="s8.logging.v1",
                        requestId=request.request_id,
                        operationId=request.operation_id,
                        provider=self._provider,
                        attempt=attempt + 1,
                        configuredTimeoutMs=int(request.timeout_seconds * 1000),
                        modelVersion=request.model_id,
                        profileRevision=request.profile_revision,
                        latencyMs=int((monotonic() - started) * 1000),
                        errorClass=error.error_class,
                        retryable=error.retryable,
                        terminalOutcome="failed",
                    ),
                )
                if not self._eligible(error) or attempt == attempts - 1:
                    raise
                await self._sleeper(self._base_delay_seconds * (2**attempt))
        raise AssertionError("retry loop must return or raise")

    def _attempt_budget(self) -> int:
        if self._mode in {"interactive-single-attempt", "explicit-user-retry", "offline-replay"}:
            return 1
        if self._mode == "live-quality-evaluation":
            return min(self._max_retries + 1, 2)
        return self._max_retries + 1

    def _eligible(self, error: NormalizedGatewayError) -> bool:
        if not error.retryable:
            return False
        if self._mode == "live-quality-evaluation":
            return error.error_class == "invalid_evidence"
        return self._mode in {"health-probe", "operator-recovery"} and error.error_class in _BOUNDED_RETRY_CLASSES
