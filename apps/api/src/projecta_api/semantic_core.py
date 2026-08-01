"""Finite HTTP client for the Semantic Core; no Fuseki access exists here."""

from collections.abc import Mapping
from typing import Protocol, cast

import httpx
from pydantic import ValidationError

from projecta_api.context import TrustedRequestContext
from projecta_api.models import CaptureRequest, CaptureResponse


class SemanticCoreProblem(Exception):
    """Sanitized downstream problem response."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)


class SemanticCoreClient(Protocol):
    """Finite operations available to the application service."""

    async def capture(
        self, context: TrustedRequestContext, key: str, request: CaptureRequest
    ) -> CaptureResponse: ...

    async def request(
        self,
        context: TrustedRequestContext,
        method: str,
        path: str,
        body: object | None = None,
        key: str | None = None,
    ) -> object: ...


class HttpSemanticCoreClient:
    """Private HTTP adapter that forwards only trusted metadata and typed bodies."""

    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    async def capture(
        self, context: TrustedRequestContext, key: str, request: CaptureRequest
    ) -> CaptureResponse:
        headers = _headers(context, key)
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=10.0, transport=self._transport
            ) as client:
                response = await client.post("/v1/quick-notes/captures", json=request.model_dump(by_alias=True), headers=headers)
            payload: object = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SemanticCoreProblem(503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core is temporarily unavailable") from error
        if response.is_error:
            raise _problem(response.status_code, payload)
        try:
            return CaptureResponse.model_validate(
                {"requestId": context.request_id, "replayed": response.status_code == 200, **_mapping(payload)}
            )
        except (ValidationError, SemanticCoreProblem) as error:
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned an invalid contract"
            ) from error

    async def request(
        self,
        context: TrustedRequestContext,
        method: str,
        path: str,
        body: object | None = None,
        key: str | None = None,
    ) -> object:
        headers = _headers(context, key)
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=10.0, transport=self._transport
            ) as client:
                response = await client.request(method, path, json=body, headers=headers)
            payload: object = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SemanticCoreProblem(503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core is temporarily unavailable") from error
        if response.is_error:
            raise _problem(response.status_code, payload)
        return {**_mapping(payload), "_projecta_http_status": response.status_code}


def _mapping(value: object) -> Mapping[str, object]:
    """Narrow unknown JSON before it enters typed schemas."""
    if not isinstance(value, dict):
        raise SemanticCoreProblem(
            502, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid JSON"
        )
    mapping = cast(Mapping[object, object], value)
    return {str(key): item for key, item in mapping.items()}


def _headers(context: TrustedRequestContext, key: str | None = None) -> dict[str, str]:
    """Build the private, deployment-established context headers."""
    headers = {
        "X-Projecta-Project-Id": context.project_id,
        "X-Projecta-Actor-Id": context.actor_id,
        "X-Request-Id": context.request_id,
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _problem(status_code: int, payload: object) -> SemanticCoreProblem:
    """Turn a finite Core problem response into the API's private exception."""
    problem = _mapping(payload)
    return SemanticCoreProblem(
        status_code,
        str(problem.get("code", "INTERNAL_ERROR")),
        str(problem.get("detail", "Semantic Core request failed")),
    )
