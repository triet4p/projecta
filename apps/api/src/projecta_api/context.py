"""Trusted request context established by deployment middleware."""

from dataclasses import dataclass
from secrets import compare_digest

from fastapi import Header, HTTPException, Request, status


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
