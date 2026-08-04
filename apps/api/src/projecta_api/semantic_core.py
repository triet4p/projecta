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

    async def entity_link_context(
        self, context: TrustedRequestContext, limit: int = 50
    ) -> list[dict[str, str]]: ...

    async def ingest_extraction(
        self, context: TrustedRequestContext, key: str, body: object
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
        except httpx.HTTPError as error:
            raise SemanticCoreProblem(503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core is temporarily unavailable") from error
        if response.is_error:
            try:
                payload: object = response.json()
            except ValueError:
                payload = {}
            raise _problem(response.status_code, payload)
        if not response.content:
            return {"_projecta_http_status": response.status_code}
        try:
            payload = response.json()
        except ValueError as error:
            raise SemanticCoreProblem(503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid JSON") from error
        return {**_mapping(payload), "_projecta_http_status": response.status_code}

    async def entity_link_context(
        self, context: TrustedRequestContext, limit: int = 50
    ) -> list[dict[str, str]]:
        """Read only bounded same-project entity IDs, types, and labels."""
        if limit < 1 or limit > 100:
            raise ValueError("entity link context limit must be between 1 and 100")
        payload = await self.request(context, "GET", f"/v1/entities/link-context?limit={limit}")
        if not isinstance(payload, dict):
            raise SemanticCoreProblem(503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid link context")
        typed_payload = cast(dict[str, object], payload)
        if not isinstance(typed_payload.get("entities"), list):
            raise SemanticCoreProblem(503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid link context")
        result: list[dict[str, str]] = []
        items = cast(list[object], typed_payload["entities"])
        for item in items:
            if not isinstance(item, dict):
                raise SemanticCoreProblem(503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid link context")
            typed_item = cast(dict[str, object], item)
            if not all(isinstance(typed_item.get(key), str) for key in ("id", "type", "label")):
                raise SemanticCoreProblem(503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid link context")
            result.append({key: str(typed_item[key]) for key in ("id", "type", "label")})
        return result

    async def ingest_extraction(
        self, context: TrustedRequestContext, key: str, body: object
    ) -> object:
        """Persist a normalized M3 batch through the finite Core operation."""
        return await self.request(context, "POST", "/v1/quick-notes/extractions", body, key)


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
