"""Safe structured events for provider attempts."""

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProviderAttemptEvent(BaseModel):
    """Allowlisted provider-attempt fields; payloads never enter this model."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["provider.attempt.started", "provider.attempt.completed"]
    schema_version: Literal["s8.logging.v1"] = Field(alias="schemaVersion")
    request_id: str = Field(min_length=1, max_length=128, alias="requestId")
    operation_id: str = Field(min_length=1, max_length=128, alias="operationId")
    provider: str = Field(min_length=1, max_length=64)
    attempt: int = Field(ge=1)
    configured_timeout_ms: int = Field(gt=0, le=120_000, alias="configuredTimeoutMs")
    model_version: str = Field(min_length=1, max_length=128, alias="modelVersion")
    profile_revision: str = Field(min_length=1, max_length=128, alias="profileRevision")
    latency_ms: int | None = Field(default=None, ge=0, alias="latencyMs")
    error_class: str | None = Field(default=None, max_length=64, alias="errorClass")
    retryable: bool = False
    terminal_outcome: Literal["success", "failed"] | None = Field(
        default=None, alias="terminalOutcome"
    )
    input_tokens: int | None = Field(default=None, ge=0, alias="inputTokens")
    prompt_cache_hit_tokens: int | None = Field(
        default=None, ge=0, alias="promptCacheHitTokens"
    )
    prompt_cache_miss_tokens: int | None = Field(
        default=None, ge=0, alias="promptCacheMissTokens"
    )
    output_tokens: int | None = Field(default=None, ge=0, alias="outputTokens")
    reasoning_tokens: int | None = Field(default=None, ge=0, alias="reasoningTokens")


def emit_provider_attempt_event(logger: logging.Logger, event: ProviderAttemptEvent) -> None:
    """Emit only the validated allowlist as structured logger metadata."""

    logger.info(
        "projecta.provider_attempt",
        extra={"projecta_provider_attempt": event.model_dump(mode="json", by_alias=True)},
    )
