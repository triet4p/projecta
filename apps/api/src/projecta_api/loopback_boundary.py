"""Loopback Host/Origin enforcement for the local desktop API boundary.

The experience-mode API binds to ``127.0.0.1`` and injects the trusted
experience context server-side for every request, so a request reaching the
listener is normally authorized by local machine ownership. Two web-level
attacks bypass that assumption without running a local process:

- DNS rebinding: a browser page whose hostname resolves to ``127.0.0.1`` issues
  same-origin requests that reach this listener while carrying a foreign
  ``Host`` header, and the same-origin policy does not stop the page from
  reading the responses.
- Local cross-origin forgery: any web page may issue a cross-origin request to
  ``http://127.0.0.1:<port>``; this API answers with no CORS headers, but in
  experience mode the request still executes server-side.

This module refuses both at the loopback entry boundary: the request ``Host``
must name a loopback address, and any present ``Origin`` must be the served
loopback origin. The fixed local server wires it in ``local_server.py``;
embedded composition, tests, and deployment composition keep their own explicit
boundaries and are untouched by it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

LOOPBACK_HOST_NAMES = frozenset({"127.0.0.1", "localhost", "::1"})


def _hostname(value: str) -> str:
    """Return the lowercased hostname of a Host header value, port removed."""

    text = value.strip()
    if text.startswith("["):
        end = text.find("]")
        return text[1:end].lower() if end > 1 else text.lower()
    if text.count(":") == 1:
        return text.split(":", 1)[0].lower()
    return text.lower()


def host_header_allowed(host_header: str | None) -> bool:
    """Whether a request Host header names the loopback boundary.

    A missing Host header is refused: HTTP/1.1 requires it and only a
    rebinding-style request from a foreign origin would omit it.
    """

    if host_header is None:
        return False
    hostname = _hostname(host_header)
    return hostname in LOOPBACK_HOST_NAMES


def origin_header_allowed(origin_header: str | None, port: int) -> bool:
    """Whether a request Origin header belongs to the served loopback origin.

    An absent Origin header is allowed: same-origin GET/HEAD requests and
    non-browser clients do not send one. A present header must be exactly the
    served loopback origin, so a foreign page cannot forge local requests.
    """

    if origin_header is None:
        return True
    try:
        parsed = urlsplit(origin_header)
    except ValueError:
        return False
    if parsed.scheme != "http" or parsed.username or parsed.password:
        return False
    try:
        origin_port = parsed.port
    except ValueError:
        return False
    return _hostname(parsed.hostname or "") in LOOPBACK_HOST_NAMES and origin_port == port


class LoopbackBoundaryMiddleware(BaseHTTPMiddleware):
    """Refuse requests whose Host/Origin does not belong to this loopback API."""

    def __init__(self, app: Callable[..., Awaitable[Response]], port: int) -> None:
        super().__init__(app)
        self._port = port

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not host_header_allowed(request.headers.get("host")) or not origin_header_allowed(
            request.headers.get("origin"), self._port
        ):
            return JSONResponse(
                {
                    "code": "LOOPBACK_BOUNDARY_REJECTED",
                    "detail": "The request did not originate from the local loopback boundary.",
                },
                status_code=403,
            )
        return await call_next(request)
