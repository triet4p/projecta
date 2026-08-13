"""Projecta-owned role and capability decisions."""

from __future__ import annotations

from fastapi import Request

from projecta_api.context import TrustedRequestContext
from projecta_api.identity.oidc import IdentityError


def require_capability(request: Request, context: TrustedRequestContext, capability: str) -> None:
    """Require a finite capability; local/CI modes retain their existing seams."""
    if request.app.state.settings.runtime_mode != "production":
        return
    service = request.app.state.identity_service
    principal = service.principal(request.cookies.get(service.settings.session_cookie_name), context.project_id)
    if capability not in principal.capabilities:
        raise IdentityError("CAPABILITY_FORBIDDEN", 403)
