"""FastAPI composition root."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from projecta_api.config import Settings
from projecta_api.configuration.audit import ConfigurationAudit
from projecta_api.configuration.connection import OpenAIConnectionChecker
from projecta_api.configuration.environment import EnvironmentRuntimeConfigurationProvider
from projecta_api.configuration.errors import ConfigurationProblem
from projecta_api.configuration.models import LLMConfigurationSnapshot
from projecta_api.configuration.ports import RuntimeConfigurationProvider
from projecta_api.configuration.runtime import OperationalRuntimeConfigurationProvider
from projecta_api.configuration.secret_store import ApplicationEncryptedSecretStore
from projecta_api.configuration.service import LLMConfigurationService
from projecta_api.configuration.storage import LLMProfileRepository, OperationalDatabase
from projecta_api.connectors.authorization import (
    ConnectorAuthorizationError,
    ConnectorPolicy,
    LocalConnectorPrincipalAdapter,
)
from projecta_api.connectors.installation_service import ConnectorInstallationService
from projecta_api.connectors.json_mock import JsonMockAdapter, JsonMockFixture
from projecta_api.connectors.orchestration import ConnectorSyncOrchestrator, SourceCommitter
from projecta_api.connectors.public_api import ConnectorPublicProblem, ConnectorRuntime
from projecta_api.connectors.registry import ConnectorRegistry
from projecta_api.connectors.secrets import ConnectorSecretPolicy
from projecta_api.context import LocalExperienceContextMiddleware
from projecta_api.correlation import resolve_correlation
from projecta_api.evidence.local import LocalEvidenceStore
from projecta_api.extraction.service import ExtractionOrchestrator
from projecta_api.llm.gateway import LLMGateway, NormalizedGatewayError
from projecta_api.llm.openai_responses import OpenAIResponsesGateway
from projecta_api.llm.resilience import ResilientGateway
from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.repository import PostgresConnectorRepository
from projecta_api.project_workspace_store import ProjectSelectionRepository
from projecta_api.retrieval.errors import RetrievalError
from projecta_api.retrieval.service import RetrievalService
from projecta_api.routes import create_router
from projecta_api.semantic_core import (
    HttpSemanticCoreClient,
    SemanticCoreClient,
    SemanticCoreProblem,
)
from projecta_api.startup import validate_startup
from projecta_api.structured_candidate_store import StructuredCandidateEditStore
from projecta_api.structured_note_store import StructuredNoteDraftStore


async def live() -> dict[str, str]:
    """Return process liveness."""
    return {"status": "live"}


def create_app(
    settings: Settings | None = None,
    semantic_client: SemanticCoreClient | None = None,
    gateway: LLMGateway | None = None,
    runtime_configuration: RuntimeConfigurationProvider | None = None,
    connector_runtime: ConnectorRuntime | None = None,
) -> FastAPI:
    """Create the application without performing network I/O."""
    actual_settings = settings or Settings()  # pyright: ignore[reportCallIssue]
    startup_problems = validate_startup(actual_settings)
    client = semantic_client or HttpSemanticCoreClient(str(actual_settings.semantic_core_url))
    database = OperationalDatabase(actual_settings.operational_database_path)
    secret_store = ApplicationEncryptedSecretStore(
        database, actual_settings.secret_store_master_key
    )
    profile_repository = LLMProfileRepository(database)
    project_selection_repository = ProjectSelectionRepository(database)
    structured_note_draft_store = StructuredNoteDraftStore(database)
    structured_candidate_edit_store = StructuredCandidateEditStore(database)
    configuration_audit = ConfigurationAudit(database)
    composed_connector_runtime = connector_runtime or _build_connector_runtime(actual_settings, client, secret_store)
    configuration: RuntimeConfigurationProvider
    if runtime_configuration is not None:
        configuration = runtime_configuration
    elif actual_settings.runtime_mode == "experience":
        configuration = OperationalRuntimeConfigurationProvider(profile_repository, secret_store)
    else:
        configuration = EnvironmentRuntimeConfigurationProvider(actual_settings)
    if gateway is None:

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
        )
    else:
        extraction = ExtractionOrchestrator(
            ResilientGateway(
                gateway, mode="interactive-single-attempt", max_retries=0, provider="injected"
            ),
            client,
            actual_settings.llm_model,
            timeout_seconds=90.0,
        )
    retrieval = RetrievalService(client)
    app = FastAPI(title="Projecta Application API", version="0.5.1")
    app.state.settings = actual_settings
    app.state.startup_problems = startup_problems
    app.state.runtime_configuration = configuration
    app.state.profile_repository = profile_repository
    app.state.secret_store = secret_store
    app.state.configuration_audit = configuration_audit
    app.state.project_selection_repository = project_selection_repository
    app.state.structured_note_draft_store = structured_note_draft_store
    app.state.structured_candidate_edit_store = structured_candidate_edit_store
    app.state.connector_runtime = composed_connector_runtime
    app.add_middleware(LocalExperienceContextMiddleware)

    @app.exception_handler(SemanticCoreProblem)
    async def semantic_problem(request: Request, error: SemanticCoreProblem) -> JSONResponse:
        """Map downstream details to the public problem contract."""
        status_code = (
            error.status_code if error.status_code in {400, 403, 404, 409, 422, 503} else 503
        )
        code = (
            error.code
            if error.code
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
            }
            else "SEMANTIC_CONTRACT_UNAVAILABLE"
        )
        detail = {
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
            "SEMANTIC_CONTRACT_UNAVAILABLE": "The semantic service is temporarily unavailable.",
        }[code]
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
            return JSONResponse({"status": "ready", "semanticCore": "ready"})
        return JSONResponse(
            status_code=503,
            content={"status": "not-ready", "semanticCore": "unavailable"},
        )

    app.add_api_route("/health/ready", ready, methods=["GET"])
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
        )
    )
    return app


class _UnavailableSourceCommitter(SourceCommitter):
    async def commit_source(self, event: object, evidence: object) -> None:
        raise RuntimeError("connector semantic source is unavailable")


def _build_connector_runtime(
    settings: Settings, client: SemanticCoreClient, secret_store: object
) -> ConnectorRuntime | None:
    """Compose the connector boundary only when deployment supplied its complete config."""
    if settings.runtime_mode != "experience":
        return None
    try:
        database = ConnectorDatabase(settings)
        repository = PostgresConnectorRepository(database)
        registry = ConnectorRegistry()
        registry.register(JsonMockAdapter(_default_fixture(settings)))
        principal = LocalConnectorPrincipalAdapter(settings)
        policy = ConnectorPolicy(principal, repository, repository)
        installation_service = ConnectorInstallationService(
            repository, policy, registry, ConnectorSecretPolicy(secret_store)  # type: ignore[arg-type]
        )
        evidence = LocalEvidenceStore(settings.evidence_root)
        orchestrator = ConnectorSyncOrchestrator(
            repository, policy, registry, evidence, _UnavailableSourceCommitter()
        )
        return ConnectorRuntime(
            repository,
            registry,
            installation_service,
            orchestrator,
            policy,
            evidence,
            client,
        )
    except (ValueError, ConnectorAuthorizationError, OSError):
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
