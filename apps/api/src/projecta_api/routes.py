"""HTTP routes for typed capture, review, and finite read operations."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Response

from projecta_api.context import TrustedRequestContext, trusted_context
from projecta_api.models import (
    CaptureRequest,
    CaptureResponse,
    ConfirmationRequest,
    RejectionRequest,
)
from projecta_api.semantic_core import SemanticCoreClient

Context = Annotated[TrustedRequestContext, Depends(trusted_context)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def create_router(client: SemanticCoreClient) -> APIRouter:
    """Create routes bound to one finite Semantic Core client."""
    router = APIRouter()

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
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/candidates/{candidate_id}/history")
    async def history(candidate_id: str, context: Context, response: Response) -> object:
        result = await client.request(context, "GET", f"/v1/candidates/{candidate_id}/history")
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/knowledge-items/{item_id}/evidence")
    async def evidence(item_id: str, context: Context, response: Response) -> object:
        result = await client.request(context, "GET", f"/v1/knowledge-items/{item_id}/evidence")
        result = _preserve_core_status(response, result)
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
