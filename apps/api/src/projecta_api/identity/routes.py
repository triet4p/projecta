"""HTTP routes for the server-owned OIDC session boundary."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from projecta_api.correlation import resolve_correlation
from projecta_api.identity.oidc import IdentityError, IdentityService


def add_identity_routes(router: APIRouter) -> None:
    @router.get("/auth/login")
    async def login(request: Request, return_to: str = Query(default="/")) -> RedirectResponse:
        service: IdentityService = request.app.state.identity_service
        correlation = resolve_correlation(request.headers.get("X-Request-Id"), request.headers.get("X-Operation-Id"))
        location, _ = service.begin_login(return_to, correlation.request_id)
        response = RedirectResponse(location, status_code=307)
        response.headers["X-Request-Id"] = correlation.request_id
        return response

    @router.get("/auth/callback")
    async def callback(request: Request, code: str, state: str) -> RedirectResponse:
        service: IdentityService = request.app.state.identity_service
        session, return_path = await service.complete_login(code, state)
        response = RedirectResponse(return_path, status_code=303)
        response.set_cookie(
            service.settings.session_cookie_name,
            session.session_id,
            max_age=service.settings.session_max_age_seconds,
            httponly=True,
            secure=service.settings.session_cookie_secure,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            service.settings.csrf_cookie_name,
            session.csrf_token,
            max_age=service.settings.session_max_age_seconds,
            httponly=False,
            secure=service.settings.session_cookie_secure,
            samesite="lax",
            path="/",
        )
        return response

    @router.get("/v1/auth/session")
    async def session(request: Request) -> dict[str, object]:
        service: IdentityService = request.app.state.identity_service
        current = service.session(request.cookies.get(service.settings.session_cookie_name))
        request_id = getattr(request.state, "request_id", "auth-session")
        if current is None:
            if service.settings.runtime_mode != "production":
                return {"requestId": request_id, "authenticated": False}
            raise IdentityError("AUTHENTICATION_REQUIRED")
        memberships = service.repository.memberships(current.subject)
        return {
            "requestId": request_id,
            "authenticated": True,
            "identity": "authenticated-user",
            "expiresAt": current.expires_at.isoformat(),
            "projects": [
                {"projectId": item.project_id, "roles": list(item.roles), "revision": item.revision}
                for item in memberships
            ],
        }

    @router.post("/auth/logout")
    async def logout(request: Request, response: Response) -> dict[str, object]:
        service: IdentityService = request.app.state.identity_service
        service.revoke(request.cookies.get(service.settings.session_cookie_name))
        response.delete_cookie(service.settings.session_cookie_name, path="/")
        response.delete_cookie(service.settings.csrf_cookie_name, path="/")
        return {"requestId": getattr(request.state, "request_id", "auth-logout"), "authenticated": False}


def map_identity_error(error: IdentityError) -> tuple[int, str, str]:
    return error.status_code, error.code, "Authentication failed safely."
