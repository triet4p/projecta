"""Finite server-owned connector principal and policy ports."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from projecta_api.config import Settings
from projecta_api.context import TrustedActorContext
from projecta_api.operational.ports import InstallationRecord, SyncRunRecord
from projecta_api.project_workspace import configured_project_ids

ConnectorAction = Literal[
    "catalog.read",
    "installation.read",
    "installation.create",
    "installation.update",
    "installation.enable",
    "installation.disable",
    "sync.run",
    "sync.read",
    "dead-letter.read",
    "sync.retry",
]


class _IdentityRoleResolver(Protocol):
    def roles_for_actor(
        self, actor_id: str, project_id: str | None = None
    ) -> tuple[tuple[str, ...], tuple[str, ...]]: ...
ConnectorRole = Literal["connector-admin", "connector-reader"]
ConnectorCapability = Literal[
    "catalog.read",
    "installation.read",
    "installation.create",
    "installation.update",
    "installation.enable",
    "installation.disable",
    "sync.run",
    "sync.read",
    "dead-letter.read",
    "sync.retry",
    "inbound-import",
]
AuthSource = Literal["local-experience", "test", "oidc-session", "future-reviewed-provider"]

ALL_ACTIONS = frozenset(
    {
        "catalog.read",
        "installation.read",
        "installation.create",
        "installation.update",
        "installation.enable",
        "installation.disable",
        "sync.run",
        "sync.read",
        "dead-letter.read",
        "sync.retry",
    }
)
ALLOWLISTED_CONNECTORS = frozenset({"json-mock", "teams", "github-public-issues"})
CONNECTOR_CAPABILITIES = {
    "json-mock": frozenset({"inbound-import"}),
    "teams": frozenset({"inbound-import"}),
    "github-public-issues": frozenset({"inbound-import"}),
}


class ConnectorAuthorizationError(RuntimeError):
    """Safe finite authorization failure; it never embeds a resource value."""

    STATUS_BY_CODE = {
        "AUTH_PRINCIPAL_REQUIRED": 401,
        "AUTH_ADAPTER_DISABLED": 503,
        "AUTH_CONFIGURATION_INVALID": 503,
        "PROJECT_FORBIDDEN": 403,
        "RESOURCE_NOT_FOUND": 404,
        "PROJECT_SELECTION_STALE": 409,
        "INVALID_LIFECYCLE_STATE": 409,
        "INVALID_REQUEST": 400,
    }

    def __init__(self, code: str) -> None:
        if code not in self.STATUS_BY_CODE:
            code = "INVALID_REQUEST"
        self.code = code
        self.status_code = self.STATUS_BY_CODE[code]
        super().__init__(code)


SAFE_DETAILS = {
    "AUTH_PRINCIPAL_REQUIRED": "Authorization context is required.",
    "AUTH_ADAPTER_DISABLED": "This authorization adapter is unavailable.",
    "AUTH_CONFIGURATION_INVALID": "Authorization configuration is unavailable.",
    "PROJECT_FORBIDDEN": "The project is not available to this actor.",
    "RESOURCE_NOT_FOUND": "The resource is not visible in this project.",
    "PROJECT_SELECTION_STALE": "The selected revision is stale and must be revalidated.",
    "INVALID_LIFECYCLE_STATE": "The requested connector state does not allow this operation.",
    "INVALID_REQUEST": "The connector request does not meet the published contract.",
}


def public_authorization_problem(
    error: ConnectorAuthorizationError, request_id: str
) -> dict[str, object]:
    """Map internal authorization errors to a finite problem without resource details."""
    return {
        "code": error.code,
        "detail": SAFE_DETAILS[error.code],
        "requestId": request_id,
    }


@dataclass(frozen=True, slots=True)
class ConnectorAuthorizationRequest:
    """Internal request created from a server-owned context dependency."""

    action: ConnectorAction
    actor_context: TrustedActorContext | None
    project_id: str | None = None
    installation_id: str | None = None
    connector_type: str | None = None
    requested_capability: str | None = None
    expected_installation_revision: int | None = None
    run_id: str | None = None
    expected_run_revision: int | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if self.action not in ALL_ACTIONS:
            raise ConnectorAuthorizationError("INVALID_REQUEST")


@dataclass(frozen=True, slots=True)
class ConnectorPrincipal:
    """Server-derived identity, scope, roles, capabilities, and correlation."""

    principal_id: str
    actor_id: str
    allowed_projects: tuple[str, ...]
    roles: tuple[ConnectorRole, ...]
    capabilities: tuple[ConnectorCapability, ...]
    auth_source: AuthSource
    request_id: str
    operation_id: str


@dataclass(frozen=True, slots=True)
class ProjectMembershipDecision:
    allowed: bool


@dataclass(frozen=True, slots=True)
class AuthorizedConnectorOperation:
    principal: ConnectorPrincipal
    action: ConnectorAction
    project_id: str | None
    installation: InstallationRecord | None
    run: SyncRunRecord | None


class ConnectorPrincipalPort(Protocol):
    async def resolve(self, request: ConnectorAuthorizationRequest) -> ConnectorPrincipal: ...

    async def project_membership(
        self, principal: ConnectorPrincipal, project_id: str
    ) -> ProjectMembershipDecision: ...

    def refresh_catalog(self, project_ids: tuple[str, ...]) -> None:
        """Replace the snapshot allowlist with the just-published catalog."""
        ...


class InstallationLookup(Protocol):
    def get_installation(self, project_id: str, installation_id: str) -> InstallationRecord | None: ...


class RunLookup(Protocol):
    def get_run(self, project_id: str, installation_id: str, run_id: str) -> SyncRunRecord | None: ...


class LocalConnectorPrincipalAdapter:
    """Adapt the server-owned local experience configuration to the port."""

    def __init__(self, settings: Settings) -> None:
        if settings.runtime_mode == "production":
            raise ConnectorAuthorizationError("AUTH_ADAPTER_DISABLED")
        if settings.runtime_mode != "experience":
            raise ConnectorAuthorizationError("AUTH_ADAPTER_DISABLED")
        if not settings.trusted_context_secret.strip() or not settings.experience_actor_id:
            raise ConnectorAuthorizationError("AUTH_CONFIGURATION_INVALID")
        try:
            projects = configured_project_ids(settings.experience_project_catalog)
        except ValueError as exc:
            raise ConnectorAuthorizationError("AUTH_CONFIGURATION_INVALID") from exc
        if not projects:
            raise ConnectorAuthorizationError("AUTH_CONFIGURATION_INVALID")
        self._actor_id = settings.experience_actor_id
        self._projects = projects
        self._admin_enabled = settings.connector_local_admin_enabled

    def refresh_catalog(self, project_ids: tuple[str, ...]) -> None:
        """Replace the snapshot allowlist with the just-published catalog.

        Called only after the registry write succeeds, inside the caller's
        maintenance fence. An empty catalog clears the snapshot; callers that
        require at least one project keep failing closed at request time.
        """
        self._projects = tuple(dict.fromkeys(project_ids))

    async def resolve(self, request: ConnectorAuthorizationRequest) -> ConnectorPrincipal:
        context = request.actor_context
        if context is None or not context.actor_id or context.actor_id != self._actor_id:
            raise ConnectorAuthorizationError("AUTH_PRINCIPAL_REQUIRED")
        read_capabilities: tuple[ConnectorCapability, ...] = (
            "catalog.read",
            "installation.read",
            "sync.read",
            "dead-letter.read",
        )
        if self._admin_enabled:
            capabilities = read_capabilities + (
                "installation.create",
                "installation.update",
                "installation.enable",
                "installation.disable",
                "sync.run",
                "sync.retry",
                "inbound-import",
            )
            roles: tuple[ConnectorRole, ...] = ("connector-admin", "connector-reader")
        else:
            capabilities = read_capabilities
            roles = ("connector-reader",)
        return ConnectorPrincipal(
            principal_id="local-principal",
            actor_id=self._actor_id,
            allowed_projects=self._projects,
            roles=roles,
            capabilities=capabilities,
            auth_source="local-experience",
            request_id=context.request_id,
            operation_id=context.operation_id,
        )

    async def project_membership(
        self, principal: ConnectorPrincipal, project_id: str
    ) -> ProjectMembershipDecision:
        return ProjectMembershipDecision(project_id in principal.allowed_projects)


class DeterministicTestPrincipalAdapter:
    """Explicit test-only principal source; never selected by production composition."""

    def __init__(
        self,
        *,
        actor_id: str,
        allowed_projects: tuple[str, ...],
        admin: bool = True,
    ) -> None:
        self._actor_id = actor_id
        self._projects = tuple(dict.fromkeys(allowed_projects))
        self._admin = admin

    async def resolve(self, request: ConnectorAuthorizationRequest) -> ConnectorPrincipal:
        context = request.actor_context
        if context is None or context.actor_id != self._actor_id:
            raise ConnectorAuthorizationError("AUTH_PRINCIPAL_REQUIRED")
        read: tuple[ConnectorCapability, ...] = (
            "catalog.read",
            "installation.read",
            "sync.read",
            "dead-letter.read",
        )
        admin_caps: tuple[ConnectorCapability, ...] = (
            "installation.create",
            "installation.update",
            "installation.enable",
            "installation.disable",
            "sync.run",
            "sync.retry",
            "inbound-import",
        )
        return ConnectorPrincipal(
            principal_id="test-principal",
            actor_id=self._actor_id,
            allowed_projects=self._projects,
            roles=("connector-admin", "connector-reader") if self._admin else ("connector-reader",),
            capabilities=read + admin_caps if self._admin else read,
            auth_source="test",
            request_id=context.request_id,
            operation_id=context.operation_id,
        )

    async def project_membership(
        self, principal: ConnectorPrincipal, project_id: str
    ) -> ProjectMembershipDecision:
        return ProjectMembershipDecision(project_id in principal.allowed_projects)

    def refresh_catalog(self, project_ids: tuple[str, ...]) -> None:
        """Test adapter holds a fixed allowlist; publication refresh is a no-op."""

        _ = project_ids

class ProductionConnectorPrincipalAdapter:
    """Resolve connector authority from the validated Projecta session only."""

    def __init__(self, identity_service: object) -> None:
        self._identity_service = identity_service

    async def resolve(self, request: ConnectorAuthorizationRequest) -> ConnectorPrincipal:
        context = request.actor_context
        if context is None or not context.actor_id:
            raise ConnectorAuthorizationError("AUTH_PRINCIPAL_REQUIRED")
        try:
            resolver = cast(_IdentityRoleResolver, self._identity_service)
            allowed, roles = resolver.roles_for_actor(context.actor_id, request.project_id)
        except Exception as error:
            raise ConnectorAuthorizationError("AUTH_CONFIGURATION_INVALID") from error
        if request.project_id and request.project_id not in allowed:
            raise ConnectorAuthorizationError("PROJECT_FORBIDDEN")
        capabilities: tuple[ConnectorCapability, ...] = (
            "catalog.read", "installation.read", "sync.read", "dead-letter.read"
        )
        connector_roles: tuple[ConnectorRole, ...] = ("connector-reader",)
        if "connector-admin" in roles:
            capabilities += ("installation.create", "installation.update", "installation.enable", "installation.disable", "sync.run", "sync.retry", "inbound-import")
            connector_roles = ("connector-admin", "connector-reader")
        return ConnectorPrincipal(
            principal_id=f"oidc:{context.actor_id}",
            actor_id=context.actor_id,
            allowed_projects=allowed,
            roles=connector_roles,
            capabilities=capabilities,
            auth_source="oidc-session",
            request_id=context.request_id,
            operation_id=context.operation_id,
        )

    async def project_membership(self, principal: ConnectorPrincipal, project_id: str) -> ProjectMembershipDecision:
        return ProjectMembershipDecision(project_id in principal.allowed_projects)

    def refresh_catalog(self, project_ids: tuple[str, ...]) -> None:
        """Production authority resolves per session; publication refresh is a no-op."""

        _ = project_ids

class ConnectorPolicy:
    """Authorize each connector action independently after principal resolution."""

    def __init__(
        self,
        principal_port: ConnectorPrincipalPort,
        installation_lookup: InstallationLookup,
        run_lookup: RunLookup | None = None,
    ) -> None:
        self._principal_port = principal_port
        self._installation_lookup = installation_lookup
        self._run_lookup = run_lookup

    def refresh_principal_catalog(self, project_ids: tuple[str, ...]) -> None:
        """Refresh the principal snapshot after a journaled catalog publication."""

        self._principal_port.refresh_catalog(project_ids)

    async def authorize(
        self, request: ConnectorAuthorizationRequest
    ) -> AuthorizedConnectorOperation:
        principal = await self._principal_port.resolve(request)
        if request.action == "catalog.read":
            self._require_capability(principal, request.action)
            return AuthorizedConnectorOperation(principal, request.action, None, None, None)
        if request.project_id is None:
            raise ConnectorAuthorizationError("PROJECT_FORBIDDEN")
        membership = await self._principal_port.project_membership(principal, request.project_id)
        if not membership.allowed:
            raise ConnectorAuthorizationError("PROJECT_FORBIDDEN")
        self._require_capability(principal, request.action)
        if request.action == "installation.create":
            self._validate_connector_type(request.connector_type)
            return AuthorizedConnectorOperation(principal, request.action, request.project_id, None, None)
        if request.action == "installation.read" and request.installation_id is None:
            return AuthorizedConnectorOperation(
                principal, request.action, request.project_id, None, None
            )
        installation = await self._installation(request.project_id, request.installation_id)
        self._validate_connector_type(installation.connector_type)
        if request.connector_type is not None and request.connector_type != installation.connector_type:
            raise ConnectorAuthorizationError("INVALID_REQUEST")
        self._check_installation_revision(
            installation,
            request.expected_installation_revision,
            required=request.action
            in {
                "installation.update",
                "installation.enable",
                "installation.disable",
                "sync.run",
                "sync.retry",
            },
        )
        if request.action == "sync.run":
            if not installation.enabled:
                raise ConnectorAuthorizationError("INVALID_LIFECYCLE_STATE")
            self._validate_capability(installation, request.requested_capability or "inbound-import")
            self._require_idempotency(request)
        if request.action == "sync.retry":
            self._require_idempotency(request)
            if request.expected_run_revision is None or request.run_id is None:
                raise ConnectorAuthorizationError("PROJECT_SELECTION_STALE")
            if self._run_lookup is None:
                raise ConnectorAuthorizationError("AUTH_CONFIGURATION_INVALID")
            run = await asyncio.to_thread(
                self._run_lookup.get_run,
                request.project_id,
                installation.installation_id,
                request.run_id,
            )
            if run is None:
                raise ConnectorAuthorizationError("RESOURCE_NOT_FOUND")
            if run.revision != request.expected_run_revision:
                raise ConnectorAuthorizationError("PROJECT_SELECTION_STALE")
            if run.terminal_outcome != "failed":
                raise ConnectorAuthorizationError("INVALID_LIFECYCLE_STATE")
            return AuthorizedConnectorOperation(principal, request.action, request.project_id, installation, run)
        if request.action == "sync.read" and request.run_id is not None:
            if self._run_lookup is None:
                raise ConnectorAuthorizationError("AUTH_CONFIGURATION_INVALID")
            run = await asyncio.to_thread(
                self._run_lookup.get_run,
                request.project_id,
                installation.installation_id,
                request.run_id,
            )
            if run is None:
                raise ConnectorAuthorizationError("RESOURCE_NOT_FOUND")
            return AuthorizedConnectorOperation(
                principal, request.action, request.project_id, installation, run
            )
        return AuthorizedConnectorOperation(principal, request.action, request.project_id, installation, None)

    async def _installation(
        self, project_id: str, installation_id: str | None
    ) -> InstallationRecord:
        if not installation_id:
            raise ConnectorAuthorizationError("RESOURCE_NOT_FOUND")
        installation = await asyncio.to_thread(
            self._installation_lookup.get_installation, project_id, installation_id
        )
        if installation is None:
            raise ConnectorAuthorizationError("RESOURCE_NOT_FOUND")
        return installation

    @staticmethod
    def _require_capability(principal: ConnectorPrincipal, action: ConnectorAction) -> None:
        admin_actions: frozenset[str] = frozenset(
            {
                "installation.create",
                "installation.update",
                "installation.enable",
                "installation.disable",
                "sync.run",
                "sync.retry",
            }
        )
        if action in admin_actions and "connector-admin" not in principal.roles:
            raise ConnectorAuthorizationError("PROJECT_FORBIDDEN")
        if action not in admin_actions and action not in principal.capabilities:
            raise ConnectorAuthorizationError("PROJECT_FORBIDDEN")

    @staticmethod
    def _validate_connector_type(connector_type: str | None) -> None:
        if connector_type not in ALLOWLISTED_CONNECTORS:
            raise ConnectorAuthorizationError("INVALID_REQUEST")

    @staticmethod
    def _validate_capability(installation: InstallationRecord, requested: str) -> None:
        allowed = CONNECTOR_CAPABILITIES.get(installation.connector_type, frozenset())
        snapshot = installation.capability_snapshot.get("capabilities", [])
        snapshot_values: set[str] = set()
        if isinstance(snapshot, list):
            snapshot_values = {
                item for item in cast(list[object], snapshot) if isinstance(item, str)
            }
        if requested not in allowed or requested not in snapshot_values:
            raise ConnectorAuthorizationError("INVALID_REQUEST")

    @staticmethod
    def _check_installation_revision(
        installation: InstallationRecord, expected: int | None, *, required: bool = False
    ) -> None:
        if required and expected is None:
            raise ConnectorAuthorizationError("PROJECT_SELECTION_STALE")
        if expected is not None and expected != installation.revision:
            raise ConnectorAuthorizationError("PROJECT_SELECTION_STALE")

    @staticmethod
    def _require_idempotency(request: ConnectorAuthorizationRequest) -> None:
        if not request.idempotency_key or not request.idempotency_key.strip():
            raise ConnectorAuthorizationError("INVALID_REQUEST")
