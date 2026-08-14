"""Trusted request context established by deployment middleware."""

from dataclasses import dataclass
from secrets import compare_digest
from uuid import uuid4

from fastapi import Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse

from projecta_api.correlation import CorrelationContext, resolve_correlation
from projecta_api.project_workspace import catalog_revision, configured_project_ids


@dataclass(frozen=True, slots=True)
class TrustedRequestContext:
    """Project, actor, and correlation identities that clients cannot choose."""

    project_id: str
    actor_id: str
    request_id: str
    operation_id: str = ""

    def __post_init__(self) -> None:
        if not self.operation_id:
            object.__setattr__(self, "operation_id", f"op-{self.request_id}")


@dataclass(frozen=True, slots=True)
class TrustedActorContext:
    """Actor and correlation identities used before a project is selected."""

    actor_id: str
    request_id: str
    operation_id: str = ""

    def __post_init__(self) -> None:
        if not self.operation_id:
            object.__setattr__(self, "operation_id", f"op-{self.request_id}")


async def trusted_context(
    request: Request,
    project_id: str | None = Header(default=None, alias="X-Projecta-Project-Id"),
    actor_id: str | None = Header(default=None, alias="X-Projecta-Actor-Id"),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    operation_id: str | None = Header(default=None, alias="X-Operation-Id"),
    selection_revision: str | None = Header(default=None, alias="X-Projecta-Selection-Revision"),
    context_secret: str | None = Header(default=None, alias="X-Projecta-Context-Secret"),
) -> TrustedRequestContext:
    """Read context injected by a trusted adapter and reject direct anonymous calls."""
    expected = request.app.state.settings.trusted_context_secret
    if request.app.state.settings.runtime_mode == "production":
        try:
            return request.app.state.identity_service.context_for_request(request)
        except Exception as error:
            status_code = getattr(error, "status_code", status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(status_code, "authenticated project context is required") from error
    if request.app.state.settings.runtime_mode == "experience" and not project_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "project selection is required")
    valid = all(value and value.strip() for value in (project_id, actor_id, request_id))
    # The API must fail closed when the deployment has not established a
    # shared secret.  Comparing an absent secret as if it were valid would
    # turn the context headers into client-controlled project routing.
    valid = valid and bool(expected and expected.strip() and context_secret)
    valid = valid and compare_digest(context_secret or "", expected or "")
    if not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "trusted project context is required")
    assert project_id is not None
    assert actor_id is not None
    assert request_id is not None
    if request.app.state.settings.runtime_mode == "experience":
        try:
            visible_projects = configured_project_ids(
                request.app.state.settings.experience_project_catalog
            )
        except ValueError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "project catalog is unavailable"
            ) from error
        if project_id not in visible_projects or selection_revision != catalog_revision(visible_projects):
            repository = getattr(request.app.state, "project_selection_repository", None)
            if repository is not None:
                repository.clear(actor_id)
            raise HTTPException(status.HTTP_409_CONFLICT, "project selection is stale")
    correlation = resolve_correlation(request_id, operation_id)
    return TrustedRequestContext(
        project_id=project_id,
        actor_id=actor_id,
        request_id=correlation.request_id,
        operation_id=correlation.operation_id,
    )


async def trusted_actor_context(
    request: Request,
    actor_id: str | None = Header(default=None, alias="X-Projecta-Actor-Id"),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    operation_id: str | None = Header(default=None, alias="X-Operation-Id"),
    context_secret: str | None = Header(default=None, alias="X-Projecta-Context-Secret"),
) -> TrustedActorContext:
    """Read server-established actor context for catalog and selection operations."""
    expected = request.app.state.settings.trusted_context_secret
    if request.app.state.settings.runtime_mode == "production":
        try:
            return request.app.state.identity_service.actor_context_for_request(request)
        except Exception as error:
            status_code = getattr(error, "status_code", status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(status_code, "authenticated actor context is required") from error
    valid = all(value and value.strip() for value in (actor_id, request_id))
    valid = valid and bool(expected and expected.strip() and context_secret)
    valid = valid and compare_digest(context_secret or "", expected or "")
    if not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "trusted actor context is required")
    assert actor_id is not None
    assert request_id is not None
    correlation = resolve_correlation(request_id, operation_id)
    return TrustedActorContext(
        actor_id=actor_id,
        request_id=correlation.request_id,
        operation_id=correlation.operation_id,
    )


class LocalExperienceContextMiddleware(BaseHTTPMiddleware):
    """Inject server-owned context and canonical correlation IDs."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        settings = request.app.state.settings
        headers = dict(request.scope.get("headers", []))
        request_hint = _header(headers, b"x-request-id")
        operation_hint = _header(headers, b"x-operation-id")
        if settings.runtime_mode == "experience" and settings.trusted_context_secret:
            correlation = CorrelationContext(
                request_id=f"experience-{uuid4().hex}",
                operation_id=f"experience-op-{uuid4().hex}",
            )
        else:
            correlation = resolve_correlation(request_hint, operation_hint)
        headers[b"x-request-id"] = correlation.request_id.encode("ascii")
        headers[b"x-operation-id"] = correlation.operation_id.encode("ascii")
        if settings.runtime_mode == "experience" and settings.trusted_context_secret:
            # The browser cannot select or override these values. The middleware
            # establishes them at the server boundary before dependency resolution.
            # Project scope is injected only from the server-side selection store.
            # Catalog/selection routes intentionally run without a project header.
            headers.pop(b"x-projecta-project-id", None)
            headers[b"x-projecta-actor-id"] = (settings.experience_actor_id or "").encode("utf-8")
            headers[b"x-projecta-context-secret"] = settings.trusted_context_secret.encode("utf-8")
            repository = getattr(request.app.state, "project_selection_repository", None)
            if repository is not None and settings.experience_actor_id:
                selection = repository.get(settings.experience_actor_id)
                if selection is not None:
                    headers[b"x-projecta-project-id"] = selection.project_id.encode("utf-8")
                    headers[b"x-projecta-selection-handle"] = selection.handle.encode("utf-8")
                    headers[b"x-projecta-selection-revision"] = selection.catalog_revision.encode(
                        "utf-8"
                    )
        elif settings.runtime_mode == "production":
            # Production identity is derived from the session cookie. Browser
            # headers must never reach context dependencies or connector code.
            for name in (
                b"x-projecta-project-id",
                b"x-projecta-actor-id",
                b"x-projecta-context-secret",
                b"x-projecta-selection-handle",
                b"x-projecta-selection-revision",
            ):
                headers.pop(name, None)
        request.state.request_id = correlation.request_id
        request.state.operation_id = correlation.operation_id
        request.scope["headers"] = list(headers.items())
        response = await call_next(request)
        response.headers["X-Request-Id"] = correlation.request_id
        response.headers["X-Operation-Id"] = correlation.operation_id
        return response


def _header(headers: dict[bytes, bytes], name: bytes) -> str | None:
    value = headers.get(name)
    return value.decode("latin-1") if value is not None else None
