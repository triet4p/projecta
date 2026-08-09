"""Typed provider-neutral gateway contract for M3 extraction."""

from collections.abc import Mapping
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.extraction.contracts import (
    ExtractionResponse,
    UsageMetadata,
)

GatewayErrorClass = Literal[
    "timeout",
    "rate_limit",
    "provider_failure",
    "configuration_invalid",
    "schema_invalid",
    "empty_malformed",
    "refusal",
    "policy_rejection",
    "invalid_evidence",
    "hallucinated_link",
    "cross_project_link",
    "normalization_invalid",
]


class GatewayRequest(BaseModel):
    """Validated input supplied by orchestration to any gateway adapter."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["m3.v1"] = Field(alias="schemaVersion")
    model_id: str = Field(min_length=1, max_length=128, alias="modelId")
    system_prompt: str = Field(min_length=1, max_length=100_000, alias="systemPrompt")
    user_prompt: str = Field(min_length=1, max_length=200_000, alias="userPrompt")
    response_schema: Mapping[str, object] = Field(alias="responseSchema")
    timeout_seconds: float = Field(gt=0, le=120, default=10.0, alias="timeoutSeconds")
    request_id: str = Field(default="request-unknown", max_length=128, alias="requestId")
    operation_id: str = Field(default="operation-unknown", max_length=128, alias="operationId")
    profile_revision: str = Field(default="unknown", max_length=128, alias="profileRevision")


class GatewayResponse(BaseModel):
    """Provider-neutral structured response and optional usage counters."""

    model_config = ConfigDict(extra="forbid")

    extraction: ExtractionResponse
    usage: UsageMetadata | None = None


class LLMGateway(Protocol):
    """The only interface extraction orchestration may use for model calls."""

    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        """Return a typed response or raise a normalized gateway error."""
        ...


class NormalizedGatewayError(Exception):
    """Safe, provider-neutral error with explicit retryability."""

    def __init__(self, error_class: GatewayErrorClass, detail: str, *, retryable: bool) -> None:
        self.error_class = error_class
        self.detail = detail
        self.retryable = retryable
        super().__init__(detail)
