"""HTTP routes for typed capture, review, and finite read operations."""

from datetime import UTC, datetime
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from projecta_api.configuration.audit import ConfigurationAudit
from projecta_api.configuration.connection import ProviderConnectionChecker
from projecta_api.configuration.errors import ConfigurationProblem
from projecta_api.configuration.models import (
    LLMProfileRemove,
    LLMProfileWrite,
)
from projecta_api.configuration.ports import RuntimeConfigurationProvider
from projecta_api.configuration.service import LLMConfigurationService
from projecta_api.context import TrustedRequestContext, trusted_context
from projecta_api.models import (
    CaptureRequest,
    CaptureResponse,
    ConfirmationRequest,
    ExtractionRequest,
    RejectionRequest,
)
from projecta_api.projections import (
    project_candidate_history,
    project_current_knowledge,
    project_evidence,
)
from projecta_api.retrieval.service import RetrievalService
from projecta_api.semantic_core import SemanticCoreClient

Context = Annotated[TrustedRequestContext, Depends(trusted_context)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


class ProjectContextQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=100)


class ConnectionCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: float = Field(default=10.0, gt=0, le=15, alias="timeoutSeconds")


class ExtractionService(Protocol):
    async def extract(self, context: TrustedRequestContext, key: str, request: ExtractionRequest) -> object: ...


def create_router(
    client: SemanticCoreClient,
    extraction: ExtractionService | None = None,
    retrieval: RetrievalService | None = None,
    configuration_service: LLMConfigurationService | None = None,
    runtime_configuration: RuntimeConfigurationProvider | None = None,
    connection_checker: ProviderConnectionChecker | None = None,
    configuration_audit: ConfigurationAudit | None = None,
) -> APIRouter:
    """Create routes bound to one finite Semantic Core client."""
    router = APIRouter()

    @router.post("/v1/project-context/answers")
    async def project_context_answer(
        payload: ProjectContextQuestion, context: Context, response: Response
    ) -> object:
        if retrieval is None:
            raise ValueError("question is required")
        answer = await retrieval.answer(context, payload.question, payload.limit)
        response.headers["X-Request-Id"] = context.request_id
        return answer.model_dump(mode="json", by_alias=True)

    @router.post("/v1/project-context/inference/rebuild")
    async def rebuild_project_context(context: Context, response: Response) -> object:
        result = await client.request(context, "POST", "/v1/inference/rebuild")
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/settings/llm")
    async def read_llm_profile(context: Context, response: Response) -> object:
        if configuration_service is None:
            raise ConfigurationProblem("CONFIGURATION_DISABLED", "Runtime configuration is unavailable.", status_code=403)
        profile = configuration_service.read(context)
        response.headers["X-Request-Id"] = context.request_id
        return {"requestId": context.request_id, "profile": profile.model_dump(mode="json", by_alias=True) if profile else None}

    @router.put("/v1/settings/llm")
    async def write_llm_profile(
        payload: LLMProfileWrite, context: Context, response: Response
    ) -> object:
        if configuration_service is None:
            raise ConfigurationProblem("CONFIGURATION_DISABLED", "Runtime configuration is unavailable.", status_code=403)
        profile = configuration_service.save(context, payload)
        response.headers["X-Request-Id"] = context.request_id
        return {"requestId": context.request_id, "profile": profile.model_dump(mode="json", by_alias=True)}

    @router.post("/v1/settings/llm/rotate")
    async def rotate_llm_credential(
        payload: LLMProfileWrite, context: Context, response: Response
    ) -> object:
        if configuration_service is None:
            raise ConfigurationProblem("CONFIGURATION_DISABLED", "Runtime configuration is unavailable.", status_code=403)
        profile = configuration_service.rotate(context, payload)
        response.headers["X-Request-Id"] = context.request_id
        return {"requestId": context.request_id, "profile": profile.model_dump(mode="json", by_alias=True)}

    @router.delete("/v1/settings/llm")
    async def remove_llm_profile(
        payload: LLMProfileRemove, context: Context, response: Response
    ) -> object:
        if configuration_service is None:
            raise ConfigurationProblem("CONFIGURATION_DISABLED", "Runtime configuration is unavailable.", status_code=403)
        profile = configuration_service.remove(context, payload)
        response.headers["X-Request-Id"] = context.request_id
        return {"requestId": context.request_id, "profile": profile.model_dump(mode="json", by_alias=True) if profile else None}

    @router.post("/v1/settings/llm/connection-check")
    async def check_llm_connection(
        payload: ConnectionCheckRequest, context: Context, response: Response
    ) -> object:
        if runtime_configuration is None or connection_checker is None:
            raise ConfigurationProblem("CONFIGURATION_DISABLED", "Runtime configuration is unavailable.", status_code=403)
        started = datetime.now(UTC)
        try:
            snapshot = runtime_configuration.resolve_llm(context)
        except Exception as error:
            from projecta_api.llm.gateway import NormalizedGatewayError

            if isinstance(error, NormalizedGatewayError):
                raise ConfigurationProblem(
                    "CONFIGURATION_UNAVAILABLE",
                    "The active LLM profile is unavailable.",
                    status_code=503,
                ) from error
            raise
        result = await connection_checker.check(snapshot, payload.timeout_seconds)
        if configuration_service is not None:
            configuration_service.record_connection_check(context, snapshot.revision, result)
        if configuration_audit is not None:
            configuration_audit.record(
                scope=context.project_id,
                actor_id=context.actor_id,
                request_id=context.request_id,
                operation="test",
                outcome=result.status,
                provider_type=snapshot.provider_type,
                base_url=snapshot.base_url,
                revision_before=int(snapshot.revision) if snapshot.revision.isdigit() else None,
                latency_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
            )
        response.headers["X-Request-Id"] = context.request_id
        return {"requestId": context.request_id, **result.model_dump(mode="json", by_alias=True)}

    @router.post("/v1/quick-notes/extractions")
    async def extract(
        payload: ExtractionRequest, context: Context, idempotency_key: Key, response: Response
    ) -> object:
        if extraction is None:
            raise RuntimeError("extraction service is not configured")
        result = await extraction.extract(context, idempotency_key, payload)
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/quick-notes", response_model=CaptureResponse, status_code=201)
    async def capture(
        payload: CaptureRequest, context: Context, idempotency_key: Key, response: Response
    ) -> CaptureResponse:
        result = await client.capture(context, idempotency_key, payload)
        if result.replayed:
            response.status_code = 200
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/candidates/{candidate_id}/validations")
    async def validate(candidate_id: str, context: Context, response: Response) -> object:
        result = await client.request(context, "POST", f"/v1/candidates/{candidate_id}/validations")
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/candidates/{candidate_id}/confirmations")
    async def confirm(
        candidate_id: str,
        payload: ConfirmationRequest,
        context: Context,
        idempotency_key: Key,
        response: Response,
    ) -> object:
        result = await client.request(
            context,
            "POST",
            f"/v1/candidates/{candidate_id}/confirmations",
            payload.model_dump(mode="json", by_alias=True),
            idempotency_key,
        )
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/candidates/{candidate_id}/rejections")
    async def reject(
        candidate_id: str,
        payload: RejectionRequest,
        context: Context,
        idempotency_key: Key,
        response: Response,
    ) -> object:
        result = await client.request(
            context,
            "POST",
            f"/v1/candidates/{candidate_id}/rejections",
            payload.model_dump(mode="json", by_alias=True),
            idempotency_key,
        )
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/knowledge-items/current")
    async def current(context: Context, response: Response, type: str | None = None) -> object:
        suffix = "" if type is None else f"?type={type}"
        result = await client.request(context, "GET", f"/v1/knowledge-items/current{suffix}")
        result = _preserve_core_status(response, result)
        result = project_current_knowledge(result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/candidates/{candidate_id}/history")
    async def history(candidate_id: str, context: Context, response: Response) -> object:
        result = await client.request(context, "GET", f"/v1/candidates/{candidate_id}/history")
        result = _preserve_core_status(response, result)
        result = project_candidate_history(result, candidate_id)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/entities/link-context")
    async def entity_link_context(
        context: Context,
        response: Response,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> object:
        entities = await client.entity_link_context(context, limit)
        response.headers["X-Request-Id"] = context.request_id
        return {"requestId": context.request_id, "entities": entities}

    @router.get("/v1/knowledge-items/{item_id}/evidence")
    async def evidence(item_id: str, context: Context, response: Response) -> object:
        result = await client.request(context, "GET", f"/v1/knowledge-items/{item_id}/evidence")
        result = _preserve_core_status(response, result)
        result = project_evidence(result, item_id)
        response.headers["X-Request-Id"] = context.request_id
        return result

    return router


def _preserve_core_status(response: Response, result: object) -> object:
    """Forward a finite Core operation's success status without exposing metadata."""
    if isinstance(result, dict):
        mapping = cast(dict[str, object], result)
        status = mapping.pop("_projecta_http_status", 200)
        if isinstance(status, int):
            response.status_code = status
        return mapping
    return result
