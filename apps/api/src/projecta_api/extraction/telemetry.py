"""Redacted structured extraction telemetry without raw payload logging."""

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionTelemetryEvent(BaseModel):
    """Safe event fields for latency, usage, outcome, and correlation analysis."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["extraction.completed", "extraction.failed"]
    request_id: str = Field(min_length=1, max_length=128, alias="requestId")
    provider: str = Field(min_length=1, max_length=64)
    model_version: str = Field(min_length=1, max_length=128, alias="modelVersion")
    prompt_version: str = Field(min_length=1, max_length=128, alias="promptVersion")
    schema_version: str = Field(min_length=1, max_length=64, alias="schemaVersion")
    latency_ms: int = Field(ge=0, alias="latencyMs")
    input_tokens: int | None = Field(default=None, ge=0, alias="inputTokens")
    output_tokens: int | None = Field(default=None, ge=0, alias="outputTokens")
    reasoning_tokens: int | None = Field(default=None, ge=0, alias="reasoningTokens")
    entity_count: int = Field(default=0, ge=0, alias="entityCount")
    relation_count: int = Field(default=0, ge=0, alias="relationCount")
    link_count: int = Field(default=0, ge=0, alias="linkCount")
    error_class: str | None = Field(default=None, max_length=64, alias="errorClass")


def emit_extraction_event(logger: logging.Logger, event: ExtractionTelemetryEvent) -> None:
    """Emit only the allowlisted event object; callers never pass raw payloads."""
    logger.info(
        "projecta.extraction",
        extra={"projecta_extraction": event.model_dump(mode="json", by_alias=True)},
    )
