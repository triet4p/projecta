"""Small, provider-neutral identity records used by the application boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ProjectRole = Literal["project-reader", "reviewer", "connector-admin"]

ROLE_ORDER: tuple[ProjectRole, ...] = ("project-reader", "reviewer", "connector-admin")


@dataclass(frozen=True, slots=True)
class LoginAttempt:
    state: str
    nonce: str
    code_verifier: str
    return_path: str
    created_at: datetime
    expires_at: datetime
    correlation_id: str


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    subject: str
    actor_id: str
    tenant_id: str | None
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None
    csrf_token: str
    session_epoch: int


@dataclass(frozen=True, slots=True)
class MembershipRecord:
    subject: str
    project_id: str
    roles: tuple[ProjectRole, ...]
    revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class IdentityPrincipal:
    subject: str
    actor_id: str
    session_id: str
    project_id: str | None
    roles: tuple[ProjectRole, ...]
    session_epoch: int
    expires_at: datetime

    @property
    def capabilities(self) -> frozenset[str]:
        capabilities = {"project.read"}
        if "reviewer" in self.roles:
            capabilities.update({"candidate.review", "candidate.validate"})
        if "connector-admin" in self.roles:
            capabilities.update(
                {
                    "connector.admin",
                    "installation.create",
                    "installation.update",
                    "sync.run",
                }
            )
        return frozenset(capabilities)
