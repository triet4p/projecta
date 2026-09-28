"""FastAPI composition root."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine

from projecta_api.config import Settings
from projecta_api.configuration.audit import ConfigurationAudit
from projecta_api.configuration.connection import OpenAIConnectionChecker
from projecta_api.configuration.environment import EnvironmentRuntimeConfigurationProvider
from projecta_api.configuration.errors import ConfigurationProblem
from projecta_api.configuration.models import LLMConfigurationSnapshot
from projecta_api.configuration.ports import RuntimeConfigurationProvider, VersionedSecretStore
from projecta_api.configuration.runtime import OperationalRuntimeConfigurationProvider
from projecta_api.configuration.secret_store import ApplicationEncryptedSecretStore
from projecta_api.configuration.service import LLMConfigurationService
from projecta_api.configuration.storage import LLMProfileRepository, OperationalDatabase
from projecta_api.connectors.authorization import (
    ConnectorAuthorizationError,
    ConnectorPolicy,
    LocalConnectorPrincipalAdapter,
    ProductionConnectorPrincipalAdapter,
)
from projecta_api.connectors.github_public_issues import GitHubPublicIssuesAdapter
from projecta_api.connectors.github_public_issues_setup import (
    PostgresGitHubPublicIssuesSetupRegistry,
)
from projecta_api.connectors.installation_service import ConnectorInstallationService
from projecta_api.connectors.json_mock import JsonMockAdapter, JsonMockFixture
from projecta_api.connectors.orchestration import ConnectorSyncOrchestrator, SourceCommitter
from projecta_api.connectors.public_api import ConnectorPublicProblem, ConnectorRuntime
from projecta_api.connectors.registry import ConnectorRegistry
from projecta_api.connectors.secrets import ConnectorSecretPolicy
from projecta_api.connectors.teams import HttpTeamsGraphTransport, TeamsAdapter
from projecta_api.connectors.teams_auth import HttpCertificateTokenExchange, TeamsCredentialProvider
from projecta_api.connectors.teams_setup import PostgresTeamsSetupRegistry
from projecta_api.context import LocalExperienceContextMiddleware
from projecta_api.correlation import resolve_correlation
from projecta_api.evidence.local import LocalEvidenceStore
from projecta_api.extraction.correction_burden import (
    CorrectionBurdenTelemetryService,
    PostgresCorrectionBurdenRepository,
)
from projecta_api.extraction.local_suggestion_store import LocalSuggestionRepository
from projecta_api.extraction.local_suggestions import (
    LocalSuggestionService,
    OllamaLocalSuggestionGateway,
)
from projecta_api.extraction.review_receipts import (
    PostgresReviewDecisionReceiptRepository,
    ReviewDecisionReceiptService,
)
from projecta_api.extraction.service import ExtractionOrchestrator
from projecta_api.identity.middleware import CsrfMiddleware
from projecta_api.identity.oidc import IdentityError, IdentityService
from projecta_api.identity.readiness import oidc_ready
from projecta_api.identity.repository import InMemoryIdentityRepository, PostgresIdentityRepository
from projecta_api.identity.routes import add_identity_routes, map_identity_error
from projecta_api.llm.gateway import LLMGateway, NormalizedGatewayError
from projecta_api.llm.openai_responses import OpenAIResponsesGateway
from projecta_api.llm.resilience import ResilientGateway
from projecta_api.operational.audit import InMemorySecurityAuditSink, SecurityAuditSink
from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.repository import PostgresConnectorRepository
from projecta_api.project_workspace_store import ProjectSelectionRepository
from projecta_api.retrieval.errors import RetrievalError
from projecta_api.retrieval.service import RetrievalService
from projecta_api.routes import create_router
from projecta_api.secrets.approle import FileAppRoleTokenProvider, HttpAppRoleLogin
from projecta_api.secrets.openbao import OpenBaoHttpTransport, OpenBaoSecretStore
from projecta_api.semantic_core import (
    HttpSemanticCoreClient,
    SemanticCoreClient,
    SemanticCoreProblem,
)
from projecta_api.startup import validate_startup
from projecta_api.structured_candidate_store import StructuredCandidateEditStore
from projecta_api.structured_note_store import StructuredNoteDraftStore
_CONTROLLED_RELATION_PUBLIC_ERRORS: dict[str, tuple[frozenset[int], str]] = {
    "CONTROLLED_RELATION_REQUEST_INVALID": (
        frozenset({422}),
        "Select a predicate only for manual relation suggestions.",
    ),
    "CONTROLLED_RELATION_UNAVAILABLE": (
        frozenset({503}),
        "The relation context is temporarily unavailable; retry later.",
    ),
    "CONTROLLED_RELATION_UNSUPPORTED": (
        frozenset({409, 422}),
        "Select an allowlisted predicate for these endpoint types and direction, or choose another endpoint pair.",
    ),
    "CONTROLLED_RELATION_EVIDENCE_UNAVAILABLE": (
        frozenset({409}),
        "Choose a relation predicate supported by the current source evidence.",
    ),
    "CONTROLLED_RELATION_CONFLICT": (
        frozenset({409}),
        "Refresh the relation suggestion and review its current receipt before retrying.",
    ),
    "CONTROLLED_RELATION_NOT_DECIDABLE": (
        frozenset({409}),
        "Only a proposed relation can be confirmed or rejected.",
    ),
    "CONTROLLED_RELATION_STALE": (
        frozenset({409}),
        "Refresh the relation suggestion and revalidate both endpoints and current evidence.",
    ),
    "CONTROLLED_RELATION_REQUIRES_VALIDATION": (
        frozenset({409}),
        "Validate both manual occurrences before relating them.",
    ),
    "CONTROLLED_RELATION_REQUIRES_CONFIRMATION": (
        frozenset({409}),
        "Confirm both manual occurrences before relating them.",
    ),
    "CONTROLLED_RELATION_INVALID_PAIR": (
        frozenset({409, 422}),
        "Use two distinct endpoints sharing one current source version.",
    ),
}



async def live() -> dict[str, str]:
    """Return process liveness."""
    return {"status": "live"}


def create_app(
    settings: Settings | None = None,
    semantic_client: SemanticCoreClient | None = None,
    gateway: LLMGateway | None = None,
    runtime_configuration: RuntimeConfigurationProvider | None = None,
    connector_runtime: ConnectorRuntime | None = None,
    identity_repository: object | None = None,
) -> FastAPI:
    """Create the application without performing network I/O."""
    actual_settings = settings or Settings()  # pyright: ignore[reportCallIssue]
    security_audit = InMemorySecurityAuditSink()
    startup_problems = validate_startup(actual_settings)
    client = semantic_client or HttpSemanticCoreClient(str(actual_settings.semantic_core_url))
    database = OperationalDatabase(actual_settings.operational_database_path)
    secret_store = ApplicationEncryptedSecretStore(
        database, actual_settings.secret_store_master_key
    )
    connector_secret_store: object = secret_store
    if actual_settings.runtime_mode == "production" and actual_settings.openbao_url:
        login = HttpAppRoleLogin(
            str(actual_settings.openbao_url),
            verify=str(actual_settings.openbao_ca_file),
        )
        token_provider = FileAppRoleTokenProvider(
            actual_settings.openbao_role_id_file,
            actual_settings.openbao_secret_id_file,
            login,
        )
        connector_secret_store = OpenBaoSecretStore(
            OpenBaoHttpTransport(
                str(actual_settings.openbao_url),
                token_provider,
                verify=str(actual_settings.openbao_ca_file),
            )
        )
    profile_repository = LLMProfileRepository(database)
    project_selection_repository = ProjectSelectionRepository(database)
    identity_repository_value: object
    if identity_repository is not None:
        identity_repository_value = identity_repository
    elif actual_settings.runtime_mode == "production" and not startup_problems:
        identity_repository_value = PostgresIdentityRepository(
            create_engine(actual_settings.identity_sync_database_url(), pool_pre_ping=True, hide_parameters=True),
            audit_sink=security_audit,
        )
    else:
        identity_repository_value = InMemoryIdentityRepository()
    identity_service = IdentityService(actual_settings, identity_repository_value, audit_sink=security_audit)  # type: ignore[arg-type]
    structured_note_draft_store = StructuredNoteDraftStore(database)
    structured_candidate_edit_store = StructuredCandidateEditStore(database)
    local_model_id = actual_settings.local_suggestion_model.strip()
    local_suggestion_gateway = (
        OllamaLocalSuggestionGateway(local_model_id)
        if local_model_id and actual_settings.runtime_mode != "production"
        else None
    )
    local_suggestion_service = LocalSuggestionService(
        LocalSuggestionRepository(database),
        local_suggestion_gateway,
        model_id=local_model_id,
        production_disabled=actual_settings.runtime_mode == "production",
    )
    configuration_audit = ConfigurationAudit(database)
    composed_connector_runtime = connector_runtime or _build_connector_runtime(actual_settings, client, connector_secret_store, identity_service, security_audit)
    configuration: RuntimeConfigurationProvider
    if runtime_configuration is not None:
        configuration = runtime_configuration
    elif actual_settings.runtime_mode == "experience":
        configuration = OperationalRuntimeConfigurationProvider(profile_repository, secret_store)
    else:
        configuration = EnvironmentRuntimeConfigurationProvider(actual_settings)
    if gateway is None:

        review_receipt_service = _build_review_receipt_service(actual_settings)
        correction_burden_service = _build_correction_burden_service(actual_settings)

        def gateway_factory(snapshot: LLMConfigurationSnapshot) -> LLMGateway:
            return ResilientGateway(
                OpenAIResponsesGateway(
                    base_url=snapshot.base_url,
                    api_key=snapshot.api_key.get_secret_value(),
                ),
                mode="interactive-single-attempt",
                max_retries=0,
                provider=snapshot.provider_type,
            )

        extraction = ExtractionOrchestrator(
            None,
            client,
            None,
            timeout_seconds=90.0,
            configuration_provider=configuration,
            gateway_factory=gateway_factory,
            review_receipt_service=review_receipt_service,
            correction_burden_service=correction_burden_service,
            authoring_telemetry_service=local_suggestion_service.authoring_telemetry,
        )
    else:
        extraction = ExtractionOrchestrator(
            ResilientGateway(
                gateway, mode="interactive-single-attempt", max_retries=0, provider="injected"
            ),
            client,
            actual_settings.llm_model,
            timeout_seconds=90.0,
            review_receipt_service=_build_review_receipt_service(actual_settings),
            correction_burden_service=_build_correction_burden_service(actual_settings),
            authoring_telemetry_service=local_suggestion_service.authoring_telemetry,
        )
    retrieval = RetrievalService(client)
    app = FastAPI(title="Projecta Application API", version="0.6.0")
    app.state.settings = actual_settings
    app.state.startup_problems = startup_problems
    app.state.runtime_configuration = configuration
    app.state.profile_repository = profile_repository
    app.state.secret_store = secret_store
    app.state.connector_secret_store = connector_secret_store
    app.state.configuration_audit = configuration_audit
    app.state.project_selection_repository = project_selection_repository
    app.state.identity_repository = identity_repository_value
    app.state.identity_service = identity_service
    app.state.security_audit_sink = security_audit
    app.state.structured_note_draft_store = structured_note_draft_store
    app.state.structured_candidate_edit_store = structured_candidate_edit_store
    app.state.connector_runtime = composed_connector_runtime
    app.add_middleware(LocalExperienceContextMiddleware)
    app.add_middleware(CsrfMiddleware)

    @app.exception_handler(SemanticCoreProblem)
    async def semantic_problem(request: Request, error: SemanticCoreProblem) -> JSONResponse:
        """Map downstream details to the public problem contract."""
        relation_problem = _CONTROLLED_RELATION_PUBLIC_ERRORS.get(error.code)
        if relation_problem is None:
            safe_relation_detail = None
            status_code = (
                error.status_code
                if error.status_code in {400, 403, 404, 409, 422, 503}
                or (
                    error.code == "LOCAL_SUGGESTION_SOURCE_TOO_LARGE"
                    and error.status_code == 413
                )
                or (
                    error.code == "LOCAL_SUGGESTION_INVALID" and error.status_code == 502
                )
                else 503
            )
        else:
            relation_statuses, safe_relation_detail = relation_problem
            status_code = (
                error.status_code if error.status_code in relation_statuses else 503
            )
        code = (
            error.code
            if relation_problem is not None
            or error.code
            in {
                "INVALID_REQUEST",
                "RESOURCE_NOT_FOUND",
                "CANDIDATE_INVALID",
                "INVALID_LIFECYCLE_STATE",
                "DECISION_CONFLICT",
                "IDEMPOTENCY_KEY_REUSED",
                "PROJECT_CATALOG_UNAVAILABLE",
                "PROJECT_NOT_FOUND",
                "PROJECT_FORBIDDEN",
                "PROJECT_SELECTION_STALE",
                "PROJECT_SELECTION_REQUIRED",
                "NOTE_DRAFT_CONFLICT",
                "CANDIDATE_EDIT_CONFLICT",
                "INVALID_PROJECT_HANDLE",
                "INVALID_NAVIGATION_HANDLE",
                "REVIEW_RECEIPT_UNAVAILABLE",
                "REVIEW_RECEIPTS_UNAVAILABLE",
                "REVIEW_RECEIPT_REQUIRED",
                "REVIEW_SOURCE_RECEIPT_UNAVAILABLE",
                "REVIEW_ITEM_INVALID",
                "REVIEW_RECEIPT_STALE",
                "REVIEW_RECEIPT_CONFLICT",
                "REVIEW_UNAUTHORIZED",
                "MANUAL_CAPTURE_INVALID",
                "MANUAL_CAPTURE_NOT_VALIDATED",
                "MATERIALIZATION_NOT_AUTHORIZED",
                "LOCAL_SUGGESTION_DISABLED",
                "LOCAL_MODEL_NOT_CONFIGURED",
                "LOCAL_MODEL_UNAVAILABLE",
                "LOCAL_SUGGESTION_INVALID",
                "LOCAL_SUGGESTION_SOURCE_TOO_LARGE",
                "LOCAL_SUGGESTION_UNAVAILABLE",
                "LOCAL_SUGGESTION_CONFLICT",
                "LOCAL_SUGGESTION_STALE",
                "LOCAL_SUGGESTION_TARGET_STALE",
                "LOCAL_SUGGESTION_EDIT_INVALID",
                "LOCAL_SUGGESTION_REQUIRES_VALIDATION",
                "LOCAL_SUGGESTION_REQUIRES_CONFIRMATION",
            }
            else "SEMANTIC_CONTRACT_UNAVAILABLE"
        )
        detail = (
            safe_relation_detail
            if safe_relation_detail is not None
            else {
                "INVALID_REQUEST": "The request does not meet the published contract.",
                "RESOURCE_NOT_FOUND": "The resource is not visible in this project.",
                "CANDIDATE_INVALID": "The candidate does not conform to the semantic contract.",
                "INVALID_LIFECYCLE_STATE": "The requested transition is not allowed.",
                "DECISION_CONFLICT": "A conflicting terminal decision already exists.",
                "IDEMPOTENCY_KEY_REUSED": "The idempotency key belongs to a different request.",
                "PROJECT_CATALOG_UNAVAILABLE": "The authorized project catalog is temporarily unavailable.",
                "PROJECT_NOT_FOUND": "The project is not visible in the authorized catalog.",
                "PROJECT_FORBIDDEN": "The project is not available to this actor.",
                "PROJECT_SELECTION_STALE": "The active project selection is stale and must be revalidated.",
                "PROJECT_SELECTION_REQUIRED": "Select an authorized project before using this workspace.",
                "NOTE_DRAFT_CONFLICT": "The Note draft revision is stale or already committed.",
                "CANDIDATE_EDIT_CONFLICT": "The candidate edit revision is stale.",
                "INVALID_PROJECT_HANDLE": "The project handle is invalid.",
                "INVALID_NAVIGATION_HANDLE": "The navigation handle is invalid.",
                "REVIEW_RECEIPT_UNAVAILABLE": "Review receipt persistence is unavailable.",
                "REVIEW_RECEIPTS_UNAVAILABLE": "Review receipt persistence is temporarily unavailable.",
                "REVIEW_RECEIPT_REQUIRED": "Manual Note rejection must use the source-bound receipt route.",
                "REVIEW_SOURCE_RECEIPT_UNAVAILABLE": "The selected item has no verified source receipt.",
                "REVIEW_ITEM_INVALID": "The selected review item is invalid.",
                "REVIEW_RECEIPT_STALE": "The review source or candidate revision is stale.",
                "REVIEW_RECEIPT_CONFLICT": "The review receipt conflicts with existing history.",
                "REVIEW_UNAUTHORIZED": "The reviewer is not authorized for this item.",
                "MANUAL_CAPTURE_INVALID": "The manual source anchor could not be verified.",
                "MANUAL_CAPTURE_NOT_VALIDATED": "Validate this Note item before approval.",
                "MATERIALIZATION_NOT_AUTHORIZED": "Approved assertion materialization is not owner-authorized.",
                "LOCAL_SUGGESTION_DISABLED": "Local suggestions are disabled in this runtime.",
                "LOCAL_MODEL_NOT_CONFIGURED": "Configure a local model before requesting a suggestion.",
                "LOCAL_MODEL_UNAVAILABLE": "The configured local model runtime is unavailable.",
                "LOCAL_SUGGESTION_INVALID": "The local model returned an unsupported proposal.",
                "LOCAL_SUGGESTION_SOURCE_TOO_LARGE": "This Note is too large for one bounded local suggestion.",
                "LOCAL_SUGGESTION_UNAVAILABLE": "The local suggestion operation failed safely.",
                "LOCAL_SUGGESTION_CONFLICT": "The suggestion request is stale or conflicting.",
                "LOCAL_SUGGESTION_STALE": "The proposal revision is stale or no longer pending.",
                "LOCAL_SUGGESTION_TARGET_STALE": "The same-project link target is no longer visible.",
                "LOCAL_SUGGESTION_EDIT_INVALID": "The suggestion edit does not match the pending proposal.",
                "LOCAL_SUGGESTION_REQUIRES_VALIDATION": "Validate the manual occurrence first.",
                "LOCAL_SUGGESTION_REQUIRES_CONFIRMATION": "Confirm this occurrence before requesting a local suggestion.",
                "SEMANTIC_CONTRACT_UNAVAILABLE": "The semantic service is temporarily unavailable.",
            }[code]
        )
        return _problem(request, status_code, code, "Semantic Core request failed", detail)

    @app.exception_handler(NormalizedGatewayError)
    async def gateway_problem(request: Request, error: NormalizedGatewayError) -> JSONResponse:
        """Map each normalized provider class to one finite safe public problem."""
        status_code, code, title, detail = _gateway_problem(error.error_class)
        return _problem(
            request,
            status_code,
            code,
            title,
            detail,
        )

    @app.exception_handler(RetrievalError)
    async def retrieval_problem(request: Request, error: RetrievalError) -> JSONResponse:
        return _problem(
            request, 400, error.code.value.upper(), "Retrieval request failed", error.detail
        )

    @app.exception_handler(ConfigurationProblem)
    async def configuration_problem(request: Request, error: ConfigurationProblem) -> JSONResponse:
        return _problem(
            request,
            error.status_code,
            error.code,
            "Runtime configuration request failed",
            error.detail,
        )

    @app.exception_handler(ConnectorPublicProblem)
    async def connector_problem(request: Request, error: ConnectorPublicProblem) -> JSONResponse:
        detail = {
            "CONNECTOR_CONFIGURATION_UNAVAILABLE": "Connector services are temporarily unavailable.",
            "CONNECTOR_FORBIDDEN": "The connector operation is not available to this actor.",
            "CONNECTOR_NOT_FOUND": "The connector resource is not visible in this project.",
            "CONNECTOR_INVALID": "The connector request does not meet the published contract.",
            "CONNECTOR_STALE": "The connector revision is stale and must be revalidated.",
            "CONNECTOR_CONFLICT": "The connector operation conflicts with current state.",
            "CONNECTOR_DISABLED": "The connector installation is disabled.",
            "CONNECTOR_FAILED": "The connector operation failed safely.",
        }[error.code]
        return _problem(request, error.status_code, error.code, "Connector request failed", detail)

    @app.exception_handler(ConnectorAuthorizationError)
    async def connector_authorization_problem(request: Request, error: ConnectorAuthorizationError) -> JSONResponse:
        code = "CONNECTOR_FORBIDDEN" if error.status_code in {401, 403} else "CONNECTOR_NOT_FOUND"
        return _problem(request, error.status_code, code, "Connector authorization failed", "The connector operation is not available to this actor.")

    @app.exception_handler(IdentityError)
    async def identity_problem(request: Request, error: IdentityError) -> JSONResponse:
        status_code, code, detail = map_identity_error(error)
        return _problem(request, status_code, code, "Authentication failed", detail)

    @app.exception_handler(Exception)
    async def unexpected_problem(request: Request, _: Exception) -> JSONResponse:
        """Keep an application crash inside one correlated, sanitized terminal error."""
        return _problem(
            request,
            500,
            "INTERNAL_ERROR",
            "Internal error",
            "The operation failed safely.",
        )

    @app.exception_handler(HTTPException)
    async def http_problem(request: Request, error: HTTPException) -> JSONResponse:
        """Keep framework validation errors inside the API's finite problem surface."""
        if error.status_code == 401:
            return _problem(
                request,
                401,
                "PROJECT_CONTEXT_REQUIRED",
                "Project context required",
                "A trusted project context is required.",
            )
        if error.status_code == 409:
            return _problem(
                request,
                409,
                "PROJECT_SELECTION_REQUIRED"
                if "required" in str(error.detail)
                else "PROJECT_SELECTION_STALE",
                "Project selection is not current",
                "Select an authorized project before using this workspace.",
            )
        if error.status_code == 503:
            return _problem(
                request,
                503,
                "PROJECT_CATALOG_UNAVAILABLE",
                "Project catalog unavailable",
                "The authorized project catalog is temporarily unavailable.",
            )
        return _problem(
            request,
            400,
            "INVALID_REQUEST",
            "Invalid request",
            "The request does not meet the published contract.",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_problem(request: Request, _: RequestValidationError) -> JSONResponse:
        """Avoid exposing Pydantic internals while reporting malformed public input."""
        return _problem(
            request,
            400,
            "INVALID_REQUEST",
            "Invalid request",
            "The request does not meet the published contract.",
        )

    app.add_api_route("/health/live", live, methods=["GET"])

    async def ready() -> JSONResponse:
        if app.state.startup_problems:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not-ready",
                    "reasonCode": "CONFIGURATION_INVALID",
                    "problems": [problem.code for problem in app.state.startup_problems],
                },
            )
        checker = getattr(client, "readiness", None)
        if checker is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not-ready",
                    "semanticCore": "unavailable",
                    "reasonCode": "SEMANTIC_CORE_CONFIGURATION_INVALID",
                },
            )
        if await checker():
            if not await oidc_ready(actual_settings):
                return JSONResponse(status_code=503, content={"status": "not-ready", "semanticCore": "ready", "oidc": "unavailable", "reasonCode": "OIDC_PROVIDER_UNAVAILABLE"})
            if isinstance(app.state.connector_secret_store, OpenBaoSecretStore):
                secret_status = app.state.connector_secret_store.readiness()
                app.state.secret_manager_status = secret_status
                if secret_status != "ready":
                    return JSONResponse(
                        status_code=503,
                        content={
                            "status": "not-ready",
                            "semanticCore": "ready",
                            "oidc": "ready",
                            "reasonCode": "SECRET_MANAGER_UNAVAILABLE",
                        },
                    )
            return JSONResponse({"status": "ready", "semanticCore": "ready", "oidc": "ready"})
        return JSONResponse(
            status_code=503,
            content={"status": "not-ready", "semanticCore": "unavailable"},
        )

    app.add_api_route("/health/ready", ready, methods=["GET"])
    add_identity_routes(app.router)
    app.include_router(
        create_router(
            client,
            extraction,
            retrieval,
            configuration_service=LLMConfigurationService(
                profile_repository,
                secret_store,
                configuration_audit,
                runtime_mode=actual_settings.runtime_mode,
            ),
            runtime_configuration=configuration,
            connection_checker=OpenAIConnectionChecker(),
            configuration_audit=configuration_audit,
            connector_runtime=composed_connector_runtime,
            local_suggestions=local_suggestion_service,
        )
    )
    return app


class _UnavailableSourceCommitter(SourceCommitter):
    async def commit_source(self, event: object, evidence: object) -> None:
        raise RuntimeError("connector semantic source is unavailable")


def _build_connector_runtime(
    settings: Settings,
    client: SemanticCoreClient,
    secret_store: object,
    identity_service: IdentityService,
    audit_sink: SecurityAuditSink | None = None,
) -> ConnectorRuntime | None:
    """Compose the connector boundary only when deployment supplied its complete config."""
    if settings.runtime_mode not in {"experience", "production"}:
        return None
    if settings.runtime_mode == "production" and not isinstance(secret_store, OpenBaoSecretStore):
        return None
    try:
        database = ConnectorDatabase(settings)
        repository = PostgresConnectorRepository(database)
        registry = ConnectorRegistry()
        registry.register(JsonMockAdapter(_default_fixture(settings)))
        registry.register(GitHubPublicIssuesAdapter())
        if isinstance(secret_store, VersionedSecretStore):
            registry.register(
                TeamsAdapter(
                    TeamsCredentialProvider(secret_store, HttpCertificateTokenExchange()),
                    HttpTeamsGraphTransport(),
                )
            )
        principal = LocalConnectorPrincipalAdapter(settings) if settings.runtime_mode == "experience" else ProductionConnectorPrincipalAdapter(identity_service)
        policy = ConnectorPolicy(principal, repository, repository)
        installation_service = ConnectorInstallationService(
            repository,
            policy,
            registry,
            ConnectorSecretPolicy(secret_store, audit_sink),  # type: ignore[arg-type]
            PostgresTeamsSetupRegistry(database),
            PostgresGitHubPublicIssuesSetupRegistry(database),
        )
        evidence = LocalEvidenceStore(settings.evidence_root)
        orchestrator = ConnectorSyncOrchestrator(
            repository, policy, registry, evidence, _UnavailableSourceCommitter(), audit_sink=audit_sink
        )
        return ConnectorRuntime(
            repository,
            registry,
            installation_service,
            orchestrator,
            policy,
            evidence,
            client,
            audit_sink,
        )
    except (ValueError, ConnectorAuthorizationError, OSError):
        return None


def _build_review_receipt_service(settings: Settings) -> ReviewDecisionReceiptService | None:
    """Use the existing PostgreSQL operational boundary when it is configured."""

    try:
        database = ConnectorDatabase(settings)
        return ReviewDecisionReceiptService(PostgresReviewDecisionReceiptRepository(database))
    except (ValueError, OSError):
        return None


def _build_correction_burden_service(settings: Settings) -> CorrectionBurdenTelemetryService | None:
    """Use the existing PostgreSQL operational boundary when configured."""

    try:
        database = ConnectorDatabase(settings)
        return CorrectionBurdenTelemetryService(PostgresCorrectionBurdenRepository(database))
    except (ValueError, OSError):
        return None


def _default_fixture(settings: Settings) -> JsonMockFixture:
    projects = [value.strip() for value in settings.experience_project_catalog.split(",") if value.strip()]
    if not projects:
        projects = ["project-a"]
    return JsonMockFixture.model_validate(
        {
            "fixtureVersion": "json-mock.v1",
            "connectorType": "json-mock",
            "resources": [
                {
                    "externalReference": f"fixture://{project}/message-001",
                    "occurredAt": "2026-08-10T00:00:00Z",
                    "eventType": "source.created",
                    "actorHint": "json-mock-user",
                    "contentType": "application/json",
                    "content": {
                        "title": "JSON Mock import",
                        "items": [{"type": "task", "text": "Review imported source"}],
                    },
                }
                for project in projects
            ],
        }
    )


def _problem(request: Request, status: int, code: str, title: str, detail: str) -> JSONResponse:
    """Create one sanitized RFC 7807-shaped public error response."""
    correlation = resolve_correlation(
        request.headers.get("X-Request-Id"), request.headers.get("X-Operation-Id")
    )
    request_id = correlation.request_id
    operation_id = correlation.operation_id
    return JSONResponse(
        status_code=status,
        content={
            "type": f"https://w3id.org/projecta/problems/{code.lower()}",
            "title": title,
            "status": status,
            "code": code,
            "detail": detail,
            "requestId": request_id,
        },
        headers={"X-Request-Id": request_id, "X-Operation-Id": operation_id},
        media_type="application/problem+json",
    )


def _gateway_problem(error_class: str) -> tuple[int, str, str, str]:
    """Return the approved public mapping without serializing provider detail."""

    if error_class == "timeout":
        return (
            504,
            "PROVIDER_TIMEOUT",
            "Provider timeout",
            "The configured provider did not respond before the deadline.",
        )
    if error_class == "rate_limit":
        return (
            429,
            "PROVIDER_RATE_LIMITED",
            "Provider rate limited",
            "The configured provider rate limited this operation.",
        )
    if error_class in {"provider_failure"}:
        return (
            503,
            "PROVIDER_UNAVAILABLE",
            "Provider unavailable",
            "The configured provider could not complete the operation.",
        )
    if error_class in {"schema_invalid", "empty_malformed", "unsafe_output"}:
        return (
            502,
            "PROVIDER_RESPONSE_INVALID",
            "Provider response invalid",
            "The provider response did not satisfy the published contract.",
        )
    if error_class in {"refusal", "policy_rejection"}:
        return (
            502,
            "PROVIDER_REFUSED",
            "Provider refused request",
            "The configured provider refused the operation.",
        )
    if error_class in {
        "invalid_evidence",
        "hallucinated_link",
        "cross_project_link",
        "normalization_invalid",
    }:
        return (
            422,
            "CANDIDATE_INVALID",
            "Candidate invalid",
            "The provider result failed semantic evidence validation.",
        )
    if error_class == "configuration_invalid":
        return (
            503,
            "CONFIGURATION_INVALID",
            "Runtime configuration invalid",
            "The provider configuration is unavailable or invalid.",
        )
    return 500, "INTERNAL_ERROR", "Extraction failed", "The extraction operation failed safely."


app = create_app()
