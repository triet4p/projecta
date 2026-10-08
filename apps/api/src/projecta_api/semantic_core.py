"""Finite HTTP client for the Semantic Core; no Fuseki access exists here."""

import asyncio
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlencode

import httpx
from pydantic import ValidationError

from projecta_api.context import TrustedActorContext, TrustedRequestContext
from projecta_api.models import CaptureRequest, CaptureResponse, SemanticCaptureRequest

SemanticCapture = CaptureRequest | SemanticCaptureRequest


class SemanticCoreProblem(Exception):
    """Sanitized downstream problem response."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)

class SemanticCoreClient(Protocol):
    """Finite operations available to the application service."""

    async def project_graph_counts(
        self, context: TrustedActorContext, project_id: str
    ) -> Mapping[str, object]: ...

    async def delete_project_graphs(
        self, context: TrustedActorContext, project_id: str
    ) -> Mapping[str, object]: ...


    async def capture(
        self, context: TrustedRequestContext, key: str, request: SemanticCapture
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


    async def stream_project_trig(
        self, context: TrustedRequestContext, destination: Path, max_bytes: int
    ) -> int: ...
    async def validate_portable_import(
        self, actor: TrustedActorContext, project_id: str, placeholder_name: str,
        project_name: str, trig_path: Path,
    ) -> Mapping[str, object]: ...

    async def apply_portable_import(
        self, actor: TrustedActorContext, project_id: str, placeholder_name: str,
        project_name: str, adopt_placeholder: bool, trig_path: Path,
    ) -> Mapping[str, object]: ...

    async def rollback_portable_import(
        self, actor: TrustedActorContext, project_id: str, placeholder_name: str,
        project_name: str, restore_placeholder: bool, trig_path: Path,
    ) -> None: ...

    async def readiness(self) -> bool:
        """Return whether Semantic Core reports its Fuseki dependency ready."""
        ...

    async def project_catalog(
        self, context: TrustedActorContext, project_ids: list[str], limit: int = 100
    ) -> object: ...


class HttpSemanticCoreClient:
    """Private HTTP adapter that forwards only trusted metadata and typed bodies."""

    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    async def capture(
        self, context: TrustedRequestContext, key: str, request: SemanticCapture
    ) -> CaptureResponse:
        headers = _headers(context, key)
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=10.0, transport=self._transport
            ) as client:
                response = await client.post(
                    "/v1/quick-notes/captures",
                    json=request.model_dump(by_alias=True),
                    headers=headers,
                )
            payload: object = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core is temporarily unavailable"
            ) from error
        if response.is_error:
            raise _problem(response.status_code, payload)
        try:
            return CaptureResponse.model_validate(
                {
                    "requestId": context.request_id,
                    "replayed": response.status_code == 200,
                    **_mapping(payload),
                }
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
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core is temporarily unavailable"
            ) from error
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
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid JSON"
            ) from error
        return {**_mapping(payload), "_projecta_http_status": response.status_code}

    async def entity_link_context(
        self, context: TrustedRequestContext, limit: int = 50
    ) -> list[dict[str, str]]:
        """Read only bounded same-project entity IDs, types, and labels."""
        if limit < 1 or limit > 100:
            raise ValueError("entity link context limit must be between 1 and 100")
        payload = await self.request(context, "GET", f"/v1/entities/link-context?limit={limit}")
        if not isinstance(payload, dict):
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid link context"
            )
        typed_payload = cast(dict[str, object], payload)
        if not isinstance(typed_payload.get("entities"), list):
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid link context"
            )
        result: list[dict[str, str]] = []
        items = cast(list[object], typed_payload["entities"])
        for item in items:
            if not isinstance(item, dict):
                raise SemanticCoreProblem(
                    503,
                    "SEMANTIC_CONTRACT_UNAVAILABLE",
                    "Semantic Core returned invalid link context",
                )
            typed_item = cast(dict[str, object], item)
            if not all(isinstance(typed_item.get(key), str) for key in ("id", "type", "label")):
                raise SemanticCoreProblem(
                    503,
                    "SEMANTIC_CONTRACT_UNAVAILABLE",
                    "Semantic Core returned invalid link context",
                )
            result.append({key: str(typed_item[key]) for key in ("id", "type", "label")})
        return result

    async def ingest_extraction(
        self, context: TrustedRequestContext, key: str, body: object
    ) -> object:
        """Persist a normalized M3 batch through the finite Core operation."""
        return await self.request(context, "POST", "/v1/quick-notes/extractions", body, key)

    async def validate_portable_import(
        self,
        actor: TrustedActorContext,
        project_id: str,
        placeholder_name: str,
        project_name: str,
        trig_path: Path,
    ) -> Mapping[str, object]:
        return await self._portable_import_request(
            actor, project_id, "validate",
            {"placeholderName": placeholder_name, "projectName": project_name}, trig_path,
        )

    async def apply_portable_import(
        self,
        actor: TrustedActorContext,
        project_id: str,
        placeholder_name: str,
        project_name: str,
        adopt_placeholder: bool,
        trig_path: Path,
    ) -> Mapping[str, object]:
        return await self._portable_import_request(
            actor, project_id, "apply",
            {
                "placeholderName": placeholder_name,
                "projectName": project_name,
                "adoptPlaceholder": str(adopt_placeholder).lower(),
            },
            trig_path,
        )

    async def rollback_portable_import(
        self,
        actor: TrustedActorContext,
        project_id: str,
        placeholder_name: str,
        project_name: str,
        restore_placeholder: bool,
        trig_path: Path,
    ) -> None:
        await self._portable_import_request(
            actor, project_id, "rollback",
            {
                "placeholderName": placeholder_name,
                "projectName": project_name,
                "restorePlaceholder": str(restore_placeholder).lower(),
            },
            trig_path,
            allow_empty=True,
        )

    async def project_graph_counts(
        self, context: TrustedActorContext, project_id: str
    ) -> Mapping[str, object]:
        return await self._project_data_request(context, project_id, "counts", "GET")

    async def delete_project_graphs(
        self, context: TrustedActorContext, project_id: str
    ) -> Mapping[str, object]:
        return await self._project_data_request(context, project_id, "delete", "POST")

    async def _project_data_request(
        self, actor: TrustedActorContext, project_id: str, action: str, method: str
    ) -> Mapping[str, object]:
        context = TrustedRequestContext(
            project_id=project_id,
            actor_id=actor.actor_id,
            request_id=actor.request_id,
            operation_id=actor.operation_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(300.0, connect=10.0),
            ) as client:
                response = await client.request(
                    method,
                    f"/v1/projects/{project_id}/project-data/{action}",
                    headers=_headers(context),
                )
        except httpx.HTTPError as error:
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core is temporarily unavailable"
            ) from error
        if response.is_error:
            try:
                payload: object = response.json()
            except ValueError:
                payload = {}
            raise _problem(response.status_code, payload)
        try:
            return _mapping(response.json())
        except (ValueError, SemanticCoreProblem) as error:
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid project data"
            ) from error
    async def _portable_import_request(
        self,
        actor: TrustedActorContext,
        project_id: str,
        action: str,
        query: Mapping[str, str],
        trig_path: Path,
        *,
        allow_empty: bool = False,
    ) -> Mapping[str, object]:
        path = f"/v1/projects/{project_id}/portable-import/{action}?{urlencode(query)}"
        context = TrustedRequestContext(
            project_id=project_id,
            actor_id=actor.actor_id,
            request_id=actor.request_id,
            operation_id=actor.operation_id,
        )

        async def chunks():
            with trig_path.open("rb") as source:
                while data := await asyncio.to_thread(source.read, 64 * 1024):
                    yield data

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(300.0, connect=10.0),
                transport=self._transport,
            ) as client:
                response = await client.post(
                    path,
                    content=chunks(),
                    headers={**_headers(context), "Content-Type": "application/trig"},
                )
        except (httpx.HTTPError, OSError) as error:
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core is temporarily unavailable"
            ) from error
        if response.is_error:
            try:
                payload: object = response.json()
            except ValueError:
                payload = {}
            raise _problem(response.status_code, payload)
        if allow_empty and not response.content:
            return {}
        try:
            return _mapping(response.json())
        except (ValueError, SemanticCoreProblem) as error:
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid import data"
            ) from error

    async def stream_project_trig(
        self, context: TrustedRequestContext, destination: Path, max_bytes: int
    ) -> int:
        """Stream the five typed project graphs without buffering their RDF body."""
        if max_bytes < 1:
            raise ValueError("semantic export byte limit must be positive")
        expected_versions = {
            "X-Projecta-Java-Runtime": "21.0.12.1+1-LTS",
            "X-Projecta-Fuseki-Version": "6.2.0",
            "X-Projecta-Semantic-Core-Javalin": "7.2.2",
            "X-Projecta-Semantic-Core-Jena": "6.2.0",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
                transport=self._transport,
            ) as client:
                async with client.stream(
                    "GET",
                    f"/v1/projects/{context.project_id}/portable-export",
                    headers=_headers(context),
                ) as response:
                    if response.status_code == 409:
                        raise SemanticCoreProblem(
                            409, "EXPORT_BUSY", "Semantic Core export is busy"
                        )
                    if response.status_code >= 400:
                        raise SemanticCoreProblem(
                            503, "EXPORT_SOURCE_UNAVAILABLE", "Semantic Core export is unavailable"
                        )
                    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
                    if media_type != "application/trig" or any(
                        response.headers.get(name) != value
                        for name, value in expected_versions.items()
                    ):
                        raise SemanticCoreProblem(
                            503, "EXPORT_UNSUPPORTED_VERSION", "Semantic Core export tuple is unsupported"
                        )
                    try:
                        triple_count = int(response.headers["X-Projecta-Graph-Triple-Count"])
                    except (KeyError, ValueError) as error:
                        raise SemanticCoreProblem(
                            503, "EXPORT_INTEGRITY_FAILED", "Semantic Core export metadata is invalid"
                        ) from error
                    observed = 0
                    with destination.open("xb") as output:
                        async for chunk in response.aiter_bytes():
                            observed += len(chunk)
                            if observed > max_bytes:
                                raise SemanticCoreProblem(
                                    413, "EXPORT_TOO_LARGE", "Semantic Core project data exceeds the export limit"
                                )
                            await asyncio.to_thread(output.write, chunk)
                        await asyncio.to_thread(output.flush)
                        await asyncio.to_thread(os.fsync, output.fileno())
                    return triple_count
        except SemanticCoreProblem:
            raise
        except (httpx.HTTPError, OSError) as error:
            raise SemanticCoreProblem(
                503, "EXPORT_SOURCE_UNAVAILABLE", "Semantic Core export is unavailable"
            ) from error

    async def readiness(self) -> bool:
        """Check the private readiness endpoint without forwarding browser context."""
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=3.0, transport=self._transport
            ) as client:
                response = await client.get("/health/ready")
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    async def project_catalog(
        self, context: TrustedActorContext, project_ids: list[str], limit: int = 100
    ) -> object:
        """Read only the finite server-owned project allowlist from Semantic Core."""
        if not project_ids or len(project_ids) > 100:
            return {"projects": [], "catalogRevision": "catalog-r-empty"}
        headers = _actor_headers(context)
        headers["X-Projecta-Visible-Projects"] = ",".join(project_ids)
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=10.0, transport=self._transport
            ) as client:
                response = await client.get(f"/v1/projects/catalog?limit={limit}", headers=headers)
                payload: object = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SemanticCoreProblem(
                503, "PROJECT_CATALOG_UNAVAILABLE", "Project catalog is temporarily unavailable"
            ) from error
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
        "X-Operation-Id": context.operation_id,
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _actor_headers(context: TrustedActorContext) -> dict[str, str]:
    """Build private headers for operations that do not have an active project."""
    return {
        "X-Projecta-Actor-Id": context.actor_id,
        "X-Request-Id": context.request_id,
        "X-Operation-Id": context.operation_id,
    }


def _problem(status_code: int, payload: object) -> SemanticCoreProblem:
    """Turn a finite Core problem response into the API's private exception."""
    problem = _mapping(payload)
    return SemanticCoreProblem(
        status_code,
        str(problem.get("code", "INTERNAL_ERROR")),
        str(problem.get("detail", "Semantic Core request failed")),
    )
