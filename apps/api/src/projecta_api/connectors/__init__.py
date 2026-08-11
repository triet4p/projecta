"""Provider-neutral connector authorization and secret boundaries."""

from projecta_api.connectors.authorization import (
    ConnectorAction,
    ConnectorAuthorizationError,
    ConnectorAuthorizationRequest,
    ConnectorPolicy,
    ConnectorPrincipal,
    DeterministicTestPrincipalAdapter,
    LocalConnectorPrincipalAdapter,
    public_authorization_problem,
)
from projecta_api.connectors.contracts import (
    CanonicalEvent,
    ConnectorDescriptor,
    ConnectorLimits,
    InstallationSnapshot,
    OpaqueCursor,
    SanitizedConnectorError,
    SyncCommand,
)
from projecta_api.connectors.event_validation import (
    CanonicalEventValidationError,
    validate_and_canonicalize,
)
from projecta_api.connectors.installation_service import ConnectorInstallationService
from projecta_api.connectors.json_mock import JsonMockAdapter, JsonMockFixture
from projecta_api.connectors.orchestration import (
    ConnectorExecutionBudget,
    ConnectorSyncOrchestrator,
    SyncResult,
)
from projecta_api.connectors.registry import ConnectorRegistry, ConnectorRegistryError
from projecta_api.connectors.secrets import (
    ConnectorSecretError,
    ConnectorSecretPolicy,
)
from projecta_api.connectors.semantic_source import ConnectorSemanticSourceCommitter
from projecta_api.connectors.source_mapping import ConnectorSourceMappingError, map_event_to_capture

__all__ = [
    "ConnectorAction",
    "ConnectorAuthorizationError",
    "ConnectorAuthorizationRequest",
    "ConnectorPolicy",
    "ConnectorPrincipal",
    "ConnectorSecretError",
    "ConnectorSecretPolicy",
    "DeterministicTestPrincipalAdapter",
    "LocalConnectorPrincipalAdapter",
    "public_authorization_problem",
    "CanonicalEvent",
    "CanonicalEventValidationError",
    "ConnectorDescriptor",
    "ConnectorExecutionBudget",
    "ConnectorInstallationService",
    "ConnectorLimits",
    "ConnectorRegistry",
    "ConnectorRegistryError",
    "ConnectorSyncOrchestrator",
    "ConnectorSemanticSourceCommitter",
    "ConnectorSourceMappingError",
    "InstallationSnapshot",
    "JsonMockAdapter",
    "JsonMockFixture",
    "OpaqueCursor",
    "SanitizedConnectorError",
    "SyncCommand",
    "SyncResult",
    "map_event_to_capture",
    "validate_and_canonicalize",
]
