"""Trusted request context established by deployment middleware."""

from dataclasses import dataclass
from secrets import compare_digest
from uuid import uuid4

from fastapi import Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse


@dataclass(frozen=True, slots=True)
class TrustedRequestContext:
    """Project, actor, and correlation identities that clients cannot choose."""

    project_id: str
    actor_id: str
    request_id: str


async def trusted_context(
    request: Request,
    project_id: str | None = Header(default=None, alias="X-Projecta-Project-Id"),
    actor_id: str | None = Header(default=None, alias="X-Projecta-Actor-Id"),
    request_id: str | None = Header(default=None, alias="X-Request-Id"),
    context_secret: str | None = Header(default=None, alias="X-Projecta-Context-Secret"),
) -> TrustedRequestContext:
    """Read context injected by a trusted adapter and reject direct anonymous calls."""
    expected = request.app.state.settings.trusted_context_secret
    if request.app.state.settings.runtime_mode == "production":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "trusted project context is required")
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
    return TrustedRequestContext(project_id=project_id, actor_id=actor_id, request_id=request_id)


class LocalExperienceContextMiddleware(BaseHTTPMiddleware):
    """Inject fixed server-owned context for the explicit local experience mode."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        settings = request.app.state.settings
        if settings.runtime_mode != "experience":
            return await call_next(request)
        if not settings.trusted_context_secret:
            return await call_next(request)
        headers = dict(request.scope.get("headers", []))
        # The browser cannot select or override these values. The middleware
        # establishes them at the server boundary before dependency resolution.
        headers[b"x-projecta-project-id"] = settings.experience_project_id.encode("utf-8")
        headers[b"x-projecta-actor-id"] = settings.experience_actor_id.encode("utf-8")
        headers[b"x-projecta-context-secret"] = settings.trusted_context_secret.encode("utf-8")
        headers[b"x-request-id"] = f"experience-{uuid4().hex}".encode("ascii")
        request.scope["headers"] = list(headers.items())
        return await call_next(request)
