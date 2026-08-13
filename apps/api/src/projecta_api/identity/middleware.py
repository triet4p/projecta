"""Request-level CSRF enforcement for browser mutations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if (
            request.app.state.settings.runtime_mode == "production"
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.url.path not in {"/auth/callback", "/auth/login"}
            and request.cookies.get(request.app.state.settings.session_cookie_name)
            and not request.app.state.identity_service.csrf_valid(request)
        ):
            response = JSONResponse({"code": "CSRF_INVALID", "detail": "Request protection failed safely."}, status_code=403)
            response.headers["X-Request-Id"] = request.headers.get("X-Request-Id", "csrf-rejected")
            return response
        return await call_next(request)
