"""FastAPI composition root."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from projecta_api.config import Settings
from projecta_api.extraction.service import ExtractionOrchestrator
from projecta_api.llm.gateway import LLMGateway, NormalizedGatewayError
from projecta_api.llm.openai_responses import OpenAIResponsesGateway
from projecta_api.llm.resilience import ResilientGateway
from projecta_api.routes import create_router
from projecta_api.semantic_core import (
    HttpSemanticCoreClient,
    SemanticCoreClient,
    SemanticCoreProblem,
)


async def live() -> dict[str, str]:
    """Return process liveness."""
    return {"status": "live"}


def create_app(
    settings: Settings | None = None,
    semantic_client: SemanticCoreClient | None = None,
    gateway: LLMGateway | None = None,
) -> FastAPI:
    """Create the application without performing network I/O."""
    actual_settings = settings or Settings()  # pyright: ignore[reportCallIssue]
    client = semantic_client or HttpSemanticCoreClient(str(actual_settings.semantic_core_url))
    resilient_gateway = ResilientGateway(
        gateway
        or OpenAIResponsesGateway(
            base_url=str(actual_settings.llm_base_url),
            api_key=actual_settings.llm_api_key.get_secret_value(),
        ),
        max_retries=2,
    )
    extraction = ExtractionOrchestrator(
        resilient_gateway, client, actual_settings.llm_model, timeout_seconds=60.0
    )
    app = FastAPI(title="Projecta Application API", version="0.1.0")
    app.state.settings = actual_settings

    @app.exception_handler(SemanticCoreProblem)
    async def semantic_problem(request: Request, error: SemanticCoreProblem) -> JSONResponse:
        """Map downstream details to the public problem contract."""
        status_code = error.status_code if error.status_code in {400, 404, 409, 422, 503} else 503
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
            "SEMANTIC_CONTRACT_UNAVAILABLE": "The semantic service is temporarily unavailable.",
        }[code]
        return _problem(request, status_code, code, "Semantic Core request failed", detail)

    @app.exception_handler(NormalizedGatewayError)
    async def gateway_problem(request: Request, error: NormalizedGatewayError) -> JSONResponse:
        """Map provider-neutral extraction failures without exposing provider details."""
        return _problem(
            request,
            503,
            "SEMANTIC_CONTRACT_UNAVAILABLE",
            "Extraction request failed",
            "The extraction operation could not be completed safely.",
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
    app.include_router(create_router(client, extraction))
    return app


app = create_app()


def _problem(request: Request, status: int, code: str, title: str, detail: str) -> JSONResponse:
    """Create one sanitized RFC 7807-shaped public error response."""
    request_id = request.headers.get("X-Request-Id", "unknown")
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
        headers={"X-Request-Id": request_id},
        media_type="application/problem+json",
    )
