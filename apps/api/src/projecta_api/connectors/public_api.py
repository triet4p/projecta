"""Public, project-scoped connector API projections.

This module is deliberately an adapter around the connector kernel. Internal
installation/run/event identifiers never cross this boundary; clients receive
stable opaque handles and finite safe state instead.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from projecta_api.connectors.authorization import (
    ConnectorAuthorizationError,
    ConnectorAuthorizationRequest,
    ConnectorPolicy,
)
from projecta_api.connectors.contracts import (
    ConnectorCapability,
    ConnectorDescriptor,
    InstallationSnapshot,
    RetryLineage,
    SyncCommand,
)
from projecta_api.connectors.installation_service import (
    ConnectorInstallationService,
    InstallationMutation,
    InstallationPatch,
)
from projecta_api.connectors.orchestration import ConnectorSyncOrchestrator, SyncResult
from projecta_api.connectors.registry import ConnectorRegistry
from projecta_api.connectors.semantic_source import ConnectorSemanticSourceCommitter
from projecta_api.context import (
    TrustedActorContext,
    TrustedRequestContext,
    trusted_actor_context,
    trusted_context,
)
from projecta_api.evidence.ports import EvidenceStore
from projecta_api.operational.errors import IdempotencyConflict, RevisionConflict
from projecta_api.operational.ports import (
    ConnectorOperationalRepository,
    InstallationRecord,
    SyncRunRecord,
)
from projecta_api.project_workspace import opaque_project_handle
from projecta_api.semantic_core import SemanticCoreClient

PublicContext = Annotated[TrustedRequestContext, Depends(trusted_context)]
PublicActor = Annotated[TrustedActorContext, Depends(trusted_actor_context)]
PublicKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
_LOGGER = logging.getLogger("projecta.connector.public")


class ConnectorPublicProblem(RuntimeError):
    """Finite error intended for the public problem handler."""

    STATUS_BY_CODE = {
        "CONNECTOR_CONFIGURATION_UNAVAILABLE": 503,
        "CONNECTOR_FORBIDDEN": 403,
        "CONNECTOR_NOT_FOUND": 404,
        "CONNECTOR_INVALID": 400,
        "CONNECTOR_STALE": 409,
        "CONNECTOR_CONFLICT": 409,
        "CONNECTOR_DISABLED": 409,
        "CONNECTOR_FAILED": 502,
    }

    def __init__(self, code: str) -> None:
        safe_code = code if code in self.STATUS_BY_CODE else "CONNECTOR_INVALID"
        self.code = safe_code
        self.status_code = self.STATUS_BY_CODE[safe_code]
        super().__init__(safe_code)


class ConnectorCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    connector_type: str = Field(alias="connectorType")
    contract_version: str = Field(alias="contractVersion")
    display_name: str = Field(alias="displayName")
    capabilities: tuple[str, ...]
    limits: dict[str, int]


class ConnectorCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: str = Field(alias="requestId")
    items: tuple[ConnectorCatalogItem, ...]


class InstallationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_reference: str = Field(alias="fixtureReference", min_length=1, max_length=512)
    capabilities: tuple[ConnectorCapability, ...] = ("inbound-import",)


class InstallationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_reference: str | None = Field(default=None, alias="fixtureReference", max_length=512)
    capabilities: tuple[ConnectorCapability, ...] | None = None
    expected_revision: int = Field(alias="expectedRevision", ge=1)


class InstallationStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: str = Field(alias="requestId")
    handle: str
    connector_type: str = Field(alias="connectorType")
    capabilities: tuple[str, ...]
    enabled: bool
    revision: int
    secret_configured: bool = Field(alias="secretConfigured")
    fixture_configured: bool = Field(alias="fixtureConfigured")


class InstallationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: str = Field(alias="requestId")
    items: tuple[InstallationStateResponse, ...]
    next_offset: int | None = Field(alias="nextOffset", default=None)


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: str = Field(alias="requestId")
    handle: str
    state: str
    event_count: int = Field(alias="eventCount", ge=0, le=100)
    replay_count: int = Field(alias="replayCount", ge=0, le=100)
    failure_code: str | None = Field(alias="failureCode", default=None)
    dead_letter_available: bool = Field(alias="deadLetterAvailable")
    revision: int
    started_at: datetime = Field(alias="startedAt")
    terminal_at: datetime | None = Field(alias="terminalAt", default=None)


class RunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: str = Field(alias="requestId")
    items: tuple[RunResponse, ...]


class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_installation_revision: int = Field(alias="expectedInstallationRevision", ge=1)


class RetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_installation_revision: int = Field(alias="expectedInstallationRevision", ge=1)
    expected_run_revision: int = Field(alias="expectedRunRevision", ge=1)


class ConnectorRuntime:
    """Dependencies composed by the application boundary and easy to inject in tests."""

    def __init__(
        self,
        repository: ConnectorOperationalRepository,
        registry: ConnectorRegistry,
        installation_service: ConnectorInstallationService,
        orchestrator: ConnectorSyncOrchestrator,
        policy: ConnectorPolicy,
        evidence: EvidenceStore,
        semantic_client: SemanticCoreClient,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.installation_service = installation_service
        self.orchestrator = orchestrator
        self.policy = policy
        self.evidence = evidence
        self.semantic_client = semantic_client


def add_connector_routes(router: APIRouter, runtime: ConnectorRuntime | None) -> None:
    """Register finite connector routes; unavailable composition fails closed."""

    def require_runtime() -> ConnectorRuntime:
        if runtime is None:
            raise ConnectorPublicProblem("CONNECTOR_CONFIGURATION_UNAVAILABLE")
        return runtime

    @router.get("/v1/connectors/catalog", response_model=ConnectorCatalogResponse)
    async def catalog(context: PublicActor, response: Response) -> ConnectorCatalogResponse:
        current = require_runtime()
        try:
            await current.policy.authorize(
                ConnectorAuthorizationRequest(
                    action="catalog.read",
                    actor_context=context,
                )
            )
            descriptors = current.registry.catalog()
        except ConnectorAuthorizationError as error:
            raise _map_error(error) from error
        except Exception as error:  # noqa: BLE001 - safe public boundary.
            raise ConnectorPublicProblem("CONNECTOR_CONFIGURATION_UNAVAILABLE") from error
        response.headers["X-Request-Id"] = context.request_id
        return ConnectorCatalogResponse(
            requestId=context.request_id,
            items=tuple(_catalog_item(item) for item in descriptors),
        )

    @router.get(
        "/v1/projects/{project_handle}/connectors/installations",
        response_model=InstallationListResponse,
    )
    async def list_installations(
        project_handle: str,
        context: PublicContext,
        request: Request,
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=10_000),
    ) -> InstallationListResponse:
        _require_project(request, project_handle, context)
        current = require_runtime()
        try:
            await current.policy.authorize(
                ConnectorAuthorizationRequest(
                    action="installation.read",
                    actor_context=_actor(context),
                    project_id=context.project_id,
                )
            )
        except Exception as error:  # noqa: BLE001 - safe public authorization mapping.
            raise _map_error(error) from error
        records = current.repository.list_installations(context.project_id, limit=limit, offset=offset)
        response.headers["X-Request-Id"] = context.request_id
        items = tuple(_installation_response(context.request_id, record) for record in records)
        next_offset = offset + len(items) if len(items) == limit else None
        return InstallationListResponse(requestId=context.request_id, items=items, nextOffset=next_offset)

    @router.post(
        "/v1/projects/{project_handle}/connectors/installations",
        response_model=InstallationStateResponse,
        status_code=201,
    )
    async def create_installation(
        project_handle: str,
        payload: InstallationCreateRequest,
        context: PublicContext,
        request: Request,
        response: Response,
    ) -> InstallationStateResponse:
        _require_project(request, project_handle, context)
        current = require_runtime()
        installation_id = f"install-{uuid4().hex}"
        try:
            snapshot = await current.installation_service.create(
                TrustedActorContext(context.actor_id, context.request_id, context.operation_id),
                InstallationMutation(
                    installationId=installation_id,
                    projectId=context.project_id,
                    connectorType="json-mock",
                    fixtureReference=payload.fixture_reference,
                    capabilities=payload.capabilities,
                ),
            )
        except Exception as error:  # noqa: BLE001 - map below to finite safe codes.
            raise _map_error(error) from error
        response.headers["X-Request-Id"] = context.request_id
        return _snapshot_response(context.request_id, snapshot_to_record(snapshot, current.repository))

    @router.get(
        "/v1/projects/{project_handle}/connectors/installations/{installation_handle}",
        response_model=InstallationStateResponse,
    )
    async def read_installation(
        project_handle: str,
        installation_handle: str,
        context: PublicContext,
        request: Request,
        response: Response,
    ) -> InstallationStateResponse:
        current = require_runtime()
        record = _find_installation(current, request, project_handle, installation_handle, context)
        try:
            await current.policy.authorize(
                ConnectorAuthorizationRequest(
                    action="installation.read",
                    actor_context=_actor(context),
                    project_id=context.project_id,
                    installation_id=record.installation_id,
                )
            )
        except Exception as error:  # noqa: BLE001 - safe public authorization mapping.
            raise _map_error(error) from error
        response.headers["X-Request-Id"] = context.request_id
        return _installation_response(context.request_id, record)

    @router.put(
        "/v1/projects/{project_handle}/connectors/installations/{installation_handle}",
        response_model=InstallationStateResponse,
    )
    async def update_installation(
        project_handle: str,
        installation_handle: str,
        payload: InstallationUpdateRequest,
        context: PublicContext,
        request: Request,
        response: Response,
    ) -> InstallationStateResponse:
        current = require_runtime()
        record = _find_installation(current, request, project_handle, installation_handle, context)
        try:
            snapshot = await current.installation_service.update(
                _actor(context),
                context.project_id,
                record.installation_id,
                InstallationPatch(**payload.model_dump(by_alias=True)),
            )
        except Exception as error:  # noqa: BLE001
            raise _map_error(error) from error
        response.headers["X-Request-Id"] = context.request_id
        return _snapshot_response(context.request_id, snapshot_to_record(snapshot, current.repository))

    @router.post(
        "/v1/projects/{project_handle}/connectors/installations/{installation_handle}/enable",
        response_model=InstallationStateResponse,
    )
    async def enable_installation(
        project_handle: str,
        payload: SyncRequest,
        installation_handle: str,
        context: PublicContext,
        request: Request,
        response: Response,
    ) -> InstallationStateResponse:
        return await _toggle_installation(True, project_handle, installation_handle, payload, context, request, response)

    @router.post(
        "/v1/projects/{project_handle}/connectors/installations/{installation_handle}/disable",
        response_model=InstallationStateResponse,
    )
    async def disable_installation(
        project_handle: str,
        payload: SyncRequest,
        installation_handle: str,
        context: PublicContext,
        request: Request,
        response: Response,
    ) -> InstallationStateResponse:
        return await _toggle_installation(False, project_handle, installation_handle, payload, context, request, response)

    @router.post(
        "/v1/projects/{project_handle}/connectors/installations/{installation_handle}/runs",
        response_model=RunResponse,
        status_code=202,
    )
    async def run_sync(
        project_handle: str,
        installation_handle: str,
        payload: SyncRequest,
        context: PublicContext,
        request: Request,
        response: Response,
        idempotency_key: PublicKey = None,
    ) -> RunResponse:
        current = require_runtime()
        record = _find_installation(current, request, project_handle, installation_handle, context)
        key = idempotency_key or f"ui-sync-{uuid4().hex}"
        result = await _run(current, context, record, payload.expected_installation_revision, key)
        response.headers["X-Request-Id"] = context.request_id
        response.status_code = 200 if result.outcome == "replayed" else 202
        run = current.repository.get_run(context.project_id, record.installation_id, result.run_id)
        if run is None:
            raise ConnectorPublicProblem("CONNECTOR_FAILED")
        return _result_response(context.request_id, run, result)

    @router.get(
        "/v1/projects/{project_handle}/connectors/installations/{installation_handle}/runs",
        response_model=RunListResponse,
    )
    async def list_runs(
        project_handle: str,
        installation_handle: str,
        context: PublicContext,
        request: Request,
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> RunListResponse:
        current = require_runtime()
        record = _find_installation(current, request, project_handle, installation_handle, context)
        try:
            await current.policy.authorize(
                ConnectorAuthorizationRequest(
                    action="sync.read",
                    actor_context=_actor(context),
                    project_id=context.project_id,
                    installation_id=record.installation_id,
                )
            )
        except Exception as error:  # noqa: BLE001 - safe public authorization mapping.
            raise _map_error(error) from error
        runs = current.repository.list_runs(context.project_id, record.installation_id, limit=limit)
        response.headers["X-Request-Id"] = context.request_id
        return RunListResponse(requestId=context.request_id, items=tuple(_run_response(context.request_id, run) for run in runs))

    @router.get(
        "/v1/projects/{project_handle}/connectors/installations/{installation_handle}/runs/{run_handle}",
        response_model=RunResponse,
    )
    async def read_run(
        project_handle: str,
        installation_handle: str,
        run_handle: str,
        context: PublicContext,
        request: Request,
        response: Response,
    ) -> RunResponse:
        current = require_runtime()
        record = _find_installation(current, request, project_handle, installation_handle, context)
        run = _find_run(current, context.project_id, record.installation_id, run_handle)
        try:
            await current.policy.authorize(
                ConnectorAuthorizationRequest(
                    action="sync.read",
                    actor_context=_actor(context),
                    project_id=context.project_id,
                    installation_id=record.installation_id,
                    run_id=run.run_id,
                )
            )
        except Exception as error:  # noqa: BLE001 - safe public authorization mapping.
            raise _map_error(error) from error
        response.headers["X-Request-Id"] = context.request_id
        return _run_response(context.request_id, run)

    @router.post(
        "/v1/projects/{project_handle}/connectors/installations/{installation_handle}/runs/{run_handle}/retry",
        response_model=RunResponse,
        status_code=202,
    )
    async def retry_run(
        project_handle: str,
        installation_handle: str,
        run_handle: str,
        payload: RetryRequest,
        context: PublicContext,
        request: Request,
        response: Response,
    ) -> RunResponse:
        current = require_runtime()
        record = _find_installation(current, request, project_handle, installation_handle, context)
        parent = _find_run(current, context.project_id, record.installation_id, run_handle)
        key = f"ui-retry-{uuid4().hex}"
        command = SyncCommand(
            projectId=context.project_id,
            installationId=record.installation_id,
            expectedInstallationRevision=payload.expected_installation_revision,
            idempotencyKey=key,
            runId=f"run-{uuid4().hex}",
            deadline=datetime.now(UTC) + timedelta(seconds=30),
            retry=RetryLineage(
                parentRunId=parent.run_id,
                parentRevision=payload.expected_run_revision,
                attemptNumber=2,
            ),
        )
        try:
            result = await current.orchestrator.retry(
                _actor(context), command, source_committer=ConnectorSemanticSourceCommitter(current.semantic_client, current.evidence, context)
            )
        except Exception as error:  # noqa: BLE001
            raise _map_error(error) from error
        run = current.repository.get_run(context.project_id, record.installation_id, result.run_id)
        if run is None:
            raise ConnectorPublicProblem("CONNECTOR_FAILED")
        response.headers["X-Request-Id"] = context.request_id
        return _result_response(context.request_id, run, result)


def _catalog_item(descriptor: ConnectorDescriptor) -> ConnectorCatalogItem:
    return ConnectorCatalogItem(
        connectorType=descriptor.connector_type,
        contractVersion=descriptor.contract_version,
        displayName=descriptor.display_name,
        capabilities=descriptor.capabilities,
        limits=descriptor.limits.model_dump(mode="json"),
    )


def connector_handle(project_id: str, installation_id: str) -> str:
    return "ci_" + sha256(f"{project_id}|{installation_id}".encode()).hexdigest()[:32]


def run_handle(project_id: str, installation_id: str, run_id: str) -> str:
    return "cr_" + sha256(f"{project_id}|{installation_id}|{run_id}".encode()).hexdigest()[:32]


def _installation_response(request_id: str, record: InstallationRecord) -> InstallationStateResponse:
    return _snapshot_response(request_id, record)


def _snapshot_response(request_id: str, record: InstallationRecord) -> InstallationStateResponse:
    capabilities = record.capability_snapshot.get("capabilities")
    values = cast(list[object], capabilities) if isinstance(capabilities, list) else []
    safe_capabilities = tuple(value for value in values if isinstance(value, str))
    return InstallationStateResponse(
        requestId=request_id,
        handle=connector_handle(record.project_id, record.installation_id),
        connectorType=record.connector_type,
        capabilities=safe_capabilities,
        enabled=record.enabled,
        revision=record.revision,
        secretConfigured=record.secret_reference is not None,
        fixtureConfigured=isinstance(record.capability_snapshot.get("fixtureReference"), str),
    )


def _run_response(request_id: str, run: SyncRunRecord) -> RunResponse:
    return RunResponse(
        requestId=request_id,
        handle=run_handle(run.project_id, run.installation_id, run.run_id),
        state=_state(run.status, run.terminal_outcome),
        eventCount=run.event_count,
        replayCount=run.replay_count,
        failureCode=run.failure_code if run.failure_code in _SAFE_FAILURE_CODES else None,
        deadLetterAvailable=run.dead_letter_id is not None,
        revision=run.revision,
        startedAt=run.started_at,
        terminalAt=run.terminal_at,
    )


def _result_response(request_id: str, run: SyncRunRecord, result: SyncResult) -> RunResponse:
    return RunResponse(
        requestId=request_id,
        handle=run_handle(run.project_id, run.installation_id, run.run_id),
        state=_state(result.outcome, result.outcome),
        eventCount=result.event_count,
        replayCount=result.replay_count,
        failureCode=result.failure_code if result.failure_code in _SAFE_FAILURE_CODES else None,
        deadLetterAvailable=result.dead_letter_id is not None,
        revision=run.revision,
        startedAt=run.started_at,
        terminalAt=run.terminal_at,
    )


_SAFE_FAILURE_CODES = frozenset(
    {
        "ADAPTER_DEADLINE_EXCEEDED", "ADAPTER_FAILED", "ADAPTER_OUTPUT_INVALID",
        "ADAPTER_LIMIT_EXCEEDED", "EVENT_OUTPUT_INVALID", "EVENT_BODY_CONFLICT",
        "EVENT_IDEMPOTENCY_CONFLICT",
        "SOURCE_COMMIT_FAILED", "CURSOR_COMMIT_CONFLICT", "EVIDENCE_WRITE_FAILED",
    }
)


def _state(status: str, outcome: str | None) -> str:
    value = outcome or status
    return {
        "succeeded": "succeeded", "accepted": "succeeded", "empty": "empty",
        "replayed": "replayed", "failed": "failed", "cancelled": "cancelled",
        "running": "running", "in_progress": "running",
    }.get(value, "unavailable")


def _actor(context: TrustedRequestContext) -> TrustedActorContext:
    return TrustedActorContext(context.actor_id, context.request_id, context.operation_id)


async def _toggle_installation(enabled: bool, project_handle: str, installation_handle: str, payload: SyncRequest, context: TrustedRequestContext, request: Request, response: Response) -> InstallationStateResponse:
    current = getattr(request.app.state, "connector_runtime", None)
    if not isinstance(current, ConnectorRuntime):
        raise ConnectorPublicProblem("CONNECTOR_CONFIGURATION_UNAVAILABLE")
    record = _find_installation(current, request, project_handle, installation_handle, context)
    try:
        snapshot = await current.installation_service.enable_or_disable(_actor(context), context.project_id, record.installation_id, payload.expected_installation_revision, enabled)
    except Exception as error:  # noqa: BLE001
        _LOGGER.error(
            "connector installation toggle escaped terminal mapping; safe public failure returned failureType=%s",
            type(error).__name__,
        )
        raise _map_error(error) from error
    response.headers["X-Request-Id"] = context.request_id
    return _snapshot_response(context.request_id, snapshot_to_record(snapshot, current.repository))


async def _run(current: ConnectorRuntime, context: TrustedRequestContext, record: InstallationRecord, expected_revision: int, key: str) -> SyncResult:
    command = SyncCommand(
        projectId=context.project_id,
        installationId=record.installation_id,
        expectedInstallationRevision=expected_revision,
        idempotencyKey=key,
        runId=f"run-{uuid4().hex}",
        deadline=datetime.now(UTC) + timedelta(seconds=30),
    )
    try:
        return await current.orchestrator.run(
            _actor(context), command,
            source_committer=ConnectorSemanticSourceCommitter(current.semantic_client, current.evidence, context),
        )
    except Exception as error:  # noqa: BLE001
        _LOGGER.error(
            "connector sync escaped terminal mapping; safe public failure returned failureType=%s failureCode=%s",
            type(error).__name__,
            getattr(error, "code", "unclassified"),
        )
        if (
            isinstance(error, ConnectorAuthorizationError)
            and error.code == "INVALID_LIFECYCLE_STATE"
            and not record.enabled
        ):
            raise ConnectorPublicProblem("CONNECTOR_DISABLED") from error
        raise _map_error(error) from error


def _require_project(request: Request, project_handle: str, context: TrustedRequestContext) -> None:
    if (
        request.headers.get("X-Projecta-Selection-Handle") != project_handle
        or project_handle != opaque_project_handle(context.project_id)
    ):
        raise ConnectorPublicProblem("CONNECTOR_NOT_FOUND")
    if not context.project_id:
        raise ConnectorPublicProblem("CONNECTOR_FORBIDDEN")


def _find_installation(runtime: ConnectorRuntime, request: Request, project_handle: str, handle: str, context: TrustedRequestContext) -> InstallationRecord:
    _require_project(request, project_handle, context)
    records = runtime.repository.list_installations(context.project_id, limit=100)
    for record in records:
        if connector_handle(record.project_id, record.installation_id) == handle:
            return record
    raise ConnectorPublicProblem("CONNECTOR_NOT_FOUND")


def _find_run(runtime: ConnectorRuntime, project_id: str, installation_id: str, handle: str) -> SyncRunRecord:
    for record in runtime.repository.list_runs(project_id, installation_id, limit=100):
        if run_handle(project_id, installation_id, record.run_id) == handle:
            return record
    raise ConnectorPublicProblem("CONNECTOR_NOT_FOUND")


def snapshot_to_record(snapshot: InstallationSnapshot, repository: ConnectorOperationalRepository) -> InstallationRecord:
    installation_id = snapshot.installation_id
    project_id = snapshot.project_id
    record = repository.get_installation(project_id, installation_id)
    if record is None:
        raise ConnectorPublicProblem("CONNECTOR_FAILED")
    return record


def _map_error(error: Exception) -> ConnectorPublicProblem:
    if isinstance(error, ConnectorPublicProblem):
        return error
    if isinstance(error, ConnectorAuthorizationError):
        if error.code == "INVALID_LIFECYCLE_STATE":
            return ConnectorPublicProblem("CONNECTOR_CONFLICT")
        return ConnectorPublicProblem(
            {401: "CONNECTOR_FORBIDDEN", 403: "CONNECTOR_FORBIDDEN", 404: "CONNECTOR_NOT_FOUND", 409: "CONNECTOR_STALE"}.get(error.status_code, "CONNECTOR_INVALID")
        )
    if isinstance(error, (RevisionConflict, IdempotencyConflict)):
        return ConnectorPublicProblem("CONNECTOR_CONFLICT")
    if isinstance(error, KeyError):
        return ConnectorPublicProblem("CONNECTOR_NOT_FOUND")
    if isinstance(error, ValueError):
        return ConnectorPublicProblem("CONNECTOR_INVALID")
    return ConnectorPublicProblem("CONNECTOR_FAILED")
