"""Single-attempt connector orchestration, replay, cursor, and dead-letter rules."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.connectors.authorization import ConnectorAuthorizationRequest, ConnectorPolicy
from projecta_api.connectors.contracts import (
    CanonicalEvent,
    ConnectorLimits,
    ErrorCode,
    OpaqueCursor,
    PullEventsCommand,
    RawEventCandidate,
    SanitizedConnectorError,
    SyncCommand,
    SyncOutcome,
    sha256_digest,
)
from projecta_api.connectors.event_validation import (
    CanonicalEventValidationError,
    validate_and_canonicalize,
)
from projecta_api.connectors.registry import ConnectorRegistry
from projecta_api.connectors.telemetry import (
    ConnectorTelemetryEvent,
    ConnectorTelemetrySink,
    now_utc,
    safe_project_scope,
)
from projecta_api.context import TrustedActorContext
from projecta_api.evidence.ports import (
    EvidenceError,
    EvidencePutRequest,
    EvidenceReceipt,
    EvidenceStore,
)
from projecta_api.operational.audit import SecurityAuditSink, emit_safe
from projecta_api.operational.errors import IdempotencyConflict, RevisionConflict
from projecta_api.operational.ports import ConnectorOperationalRepository, SyncRunRecord


class SourceCommitter(Protocol):
    """Future Semantic Core boundary; the kernel never imports Semantic Core."""

    async def commit_source(self, event: CanonicalEvent, evidence: EvidenceReceipt) -> None: ...


class ConnectorExecutionBudget(BaseModel):
    """Finite stage budgets derived from one outer deadline; no nested retries."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    adapter_seconds: float = Field(default=10.0, gt=0, le=60)
    database_seconds: float = Field(default=5.0, gt=0, le=30)
    evidence_seconds: float = Field(default=10.0, gt=0, le=60)
    semantic_core_seconds: float = Field(default=20.0, gt=0, le=60)
    proxy_seconds: float = Field(default=30.0, gt=0, le=120)
    ui_poll_seconds: float = Field(default=30.0, gt=0, le=120)


class SyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(alias="runId")
    outcome: SyncOutcome
    event_count: int = Field(alias="eventCount", ge=0, le=100)
    replay_count: int = Field(alias="replayCount", ge=0, le=100)
    dead_letter_id: int | None = Field(default=None, alias="deadLetterId")
    failure_code: str | None = Field(default=None, alias="failureCode")


class ConnectorSyncOrchestrator:
    """Execute one adapter call and one terminal run result per operation key."""

    def __init__(
        self,
        repository: ConnectorOperationalRepository,
        policy: ConnectorPolicy,
        registry: ConnectorRegistry,
        evidence: EvidenceStore,
        source_committer: SourceCommitter,
        *,
        limits: ConnectorLimits | None = None,
        budget: ConnectorExecutionBudget | None = None,
        telemetry: ConnectorTelemetrySink | None = None,
        audit_sink: SecurityAuditSink | None = None,
    ) -> None:
        self._logger = logging.getLogger("projecta.connector.kernel")
        self._repository = repository
        self._policy = policy
        self._registry = registry
        self._evidence = evidence
        self._source = source_committer
        self._limits = limits or ConnectorLimits()
        self._budget = budget or ConnectorExecutionBudget()
        self._telemetry = telemetry
        self._audit_sink = audit_sink

    async def run(
        self,
        context: TrustedActorContext,
        command: SyncCommand,
        source_committer: SourceCommitter | None = None,
    ) -> SyncResult:
        authorized = await self._policy.authorize(
            ConnectorAuthorizationRequest(
                action="sync.run",
                actor_context=context,
                project_id=command.project_id,
                installation_id=command.installation_id,
                expected_installation_revision=command.expected_installation_revision,
                requested_capability=command.capability,
                idempotency_key=command.idempotency_key,
            )
        )
        installation = authorized.installation
        if installation is None:
            raise KeyError("connector installation not found")
        adapter = self._registry.resolve(installation.connector_type)
        try:
            run = await asyncio.to_thread(
                self._repository.start_run,
                project_id=command.project_id,
                installation_id=command.installation_id,
                run_id=command.run_id,
                idempotency_key=command.idempotency_key,
                retry_of_run_id=command.retry.parent_run_id if command.retry else None,
            )
        except Exception as error:  # noqa: BLE001 - preserve the safe public boundary mapping.
            self._logger.error(
                "connector run start failed before adapter boundary; failureType=%s",
                type(error).__name__,
            )
            raise
        self._emit_start(command, installation.connector_type)
        if run.terminal_at is not None:
            result = SyncResult(
                runId=run.run_id,
                outcome="replayed",
                eventCount=run.event_count,
                replayCount=run.replay_count,
                deadLetterId=run.dead_letter_id,
                failureCode=run.failure_code,
            )
            self._emit_terminal(command, installation.connector_type, result, run.started_at)
            return result
        await self._audit(
            command.project_id,
            command.installation_id,
            "run",
            "accepted",
            context.actor_id,
            context.request_id,
            run.revision,
        )
        try:
            cursor = await asyncio.to_thread(
                self._repository.get_cursor, command.project_id, command.installation_id
            )
        except Exception as error:  # noqa: BLE001 - preserve public boundary mapping.
            self._logger.error(
                "connector cursor read failed before adapter boundary; failureType=%s",
                type(error).__name__,
            )
            raise
        raw_provider_config = installation.capability_snapshot.get("providerConfig")
        provider_config = cast(dict[str, object], raw_provider_config) if isinstance(raw_provider_config, dict) else None
        pull_command = PullEventsCommand(
            installationId=command.installation_id,
            projectId=command.project_id,
            fixtureReference=_fixture_reference(installation.capability_snapshot),
            cursor=None
            if cursor is None or cursor.checkpoint is None
            else OpaqueCursor(value=cursor.checkpoint),
            max_events=self._limits.max_events,
            max_bytes=self._limits.max_run_bytes,
            deadline=command.deadline,
            correlationId=context.request_id,
            operationId=context.operation_id,
            capability=command.capability,
            installationRevision=installation.revision,
            providerConfig=provider_config,
        )
        try:
            remaining = _remaining_seconds(command.deadline)
            if remaining <= 0:
                raise TimeoutError
            pull = await asyncio.wait_for(
                adapter.pull_events(pull_command),
                timeout=min(remaining, self._budget.adapter_seconds),
            )
        except TimeoutError as error:
            return await self._terminal_failure(
                command,
                run,
                "ADAPTER_DEADLINE_EXCEEDED",
                "adapter deadline exceeded",
                "deadline-exceeded",
                error,
            )
        except Exception as error:  # noqa: BLE001 - adapter boundary is mapped to one safe outcome.
            return await self._terminal_failure(
                command, run, "ADAPTER_FAILED", "adapter failed", "failed", error
            )
        if pull.outcome in {"unavailable", "rate-limited", "deadline-exceeded", "malformed-output", "cancelled"}:
            return await self._terminal_failure(
                command,
                run,
                pull.failure_code or _pull_failure_code(pull.outcome),
                "adapter returned a bounded provider failure",
                pull.outcome,
                None,
            )
        if pull.outcome not in {"succeeded", "empty", "truncated"}:
            return await self._terminal_failure(
                command, run, "ADAPTER_OUTPUT_INVALID", "adapter output was not accepted", "failed", None
            )
        if (
            len(pull.events) > self._limits.max_events
            or pull.source_bytes > self._limits.max_run_bytes
        ):
            return await self._terminal_failure(
                command, run, "ADAPTER_LIMIT_EXCEEDED", "pull limits exceeded", "failed", None
            )
        return await self._process_events(
            context,
            command,
            run,
            installation.connector_type,
            pull.events,
            pull.next_cursor.value if pull.next_cursor and pull.outcome != "truncated" else None,
            cursor.revision if cursor else 0,
            source_committer or self._source,
            pull_outcome=pull.outcome,
        )

    async def retry(
        self,
        context: TrustedActorContext,
        command: SyncCommand,
        source_committer: SourceCommitter | None = None,
    ) -> SyncResult:
        """Authorize one visible retry, then execute it through the same single-attempt path."""
        if command.retry is None:
            raise ValueError("SYNC_RETRY_INVALID")
        await self._policy.authorize(
            ConnectorAuthorizationRequest(
                action="sync.retry",
                actor_context=context,
                project_id=command.project_id,
                installation_id=command.installation_id,
                expected_installation_revision=command.expected_installation_revision,
                run_id=command.retry.parent_run_id,
                expected_run_revision=command.retry.parent_revision,
                idempotency_key=command.idempotency_key,
            )
        )
        await self._audit(
            command.project_id,
            command.installation_id,
            "retry",
            "accepted",
            context.actor_id,
            context.request_id,
            command.retry.parent_revision,
        )
        return await self.run(context, command, source_committer=source_committer)

    async def _process_events(
        self,
        context: TrustedActorContext,
        command: SyncCommand,
        run: SyncRunRecord,
        connector_type: str,
        candidates: tuple[RawEventCandidate, ...],
        next_cursor: str | None,
        cursor_revision: int,
        source_committer: SourceCommitter,
        *,
        pull_outcome: SyncOutcome = "succeeded",
    ) -> SyncResult:
        pending: list[tuple[CanonicalEvent, EvidenceReceipt]] = []
        replay_count = 0
        candidate_count = len(candidates)
        candidate_ids = [candidate.event_id for candidate in candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            return await self._terminal_failure(
                command,
                run,
                "EVENT_IDEMPOTENCY_CONFLICT",
                "duplicate event identity in pull",
                "failed",
                None,
                event_count=candidate_count,
            )
        for candidate in candidates:
            try:
                observed_at = datetime.now(UTC)
                # Validate every adapter-owned field before persisting raw evidence.
                # The placeholder is structurally valid and is never committed.
                validate_and_canonicalize(
                    candidate,
                    project_id=command.project_id,
                    installation_id=command.installation_id,
                    connector_type=connector_type,
                    evidence_reference="ev_0000000000000000000000",
                    now=observed_at,
                )
                receipt = await self._put_evidence(
                    command,
                    candidate.content_bytes,
                    candidate.content_type,
                    candidate.external_reference,
                )
                event = validate_and_canonicalize(
                    candidate,
                    project_id=command.project_id,
                    installation_id=command.installation_id,
                    connector_type=connector_type,
                    evidence_reference=receipt.evidence_reference,
                    now=observed_at,
                )
            except (CanonicalEventValidationError, ValueError) as error:
                return await self._terminal_failure(
                    command,
                    run,
                    "EVENT_OUTPUT_INVALID",
                    "event validation failed",
                    "failed",
                    error,
                    event_id=candidate.event_id,
                    event_count=candidate_count,
                    replay_count=replay_count,
                )
            except (EvidenceError, TimeoutError) as error:
                return await self._terminal_failure(
                    command,
                    run,
                    "EVIDENCE_WRITE_FAILED",
                    "evidence write failed",
                    "failed",
                    error,
                    event_id=candidate.event_id,
                    event_count=candidate_count,
                    replay_count=replay_count,
                )
            try:
                claim = await asyncio.to_thread(
                    self._repository.claim_event,
                    project_id=command.project_id,
                    installation_id=command.installation_id,
                    event_id=event.event_id,
                    body_hash=event.canonical_body_hash.removeprefix("sha256:"),
                    content_reference=event.content.content_ref,
                )
            except IdempotencyConflict as error:
                return await self._terminal_failure(
                    command,
                    run,
                    "EVENT_BODY_CONFLICT",
                    "event body conflicts",
                    "failed",
                    error,
                    event_id=event.event_id,
                    event_count=candidate_count,
                    replay_count=replay_count,
                )
            if claim.outcome == "replayed":
                replay_count += 1
                continue
            if claim.outcome == "in_progress":
                return await self._terminal_failure(
                    command,
                    run,
                    "EVENT_IDEMPOTENCY_CONFLICT",
                    "event is already in progress",
                    "failed",
                    None,
                    event_id=event.event_id,
                    event_count=candidate_count,
                    replay_count=replay_count,
                )
            pending.append((event, receipt))
        for index, (event, receipt) in enumerate(pending):
            try:
                await self._commit_source(source_committer, event, receipt, command.deadline)
                is_last_new = index == len(pending) - 1
                checkpoint = next_cursor if is_last_new else None
                await asyncio.to_thread(
                    self._repository.complete_event,
                    project_id=command.project_id,
                    installation_id=command.installation_id,
                    event_id=event.event_id,
                    body_hash=event.canonical_body_hash.removeprefix("sha256:"),
                    outcome="accepted",
                    checkpoint=checkpoint,
                    expected_cursor_revision=cursor_revision,
                )
                if checkpoint is not None:
                    cursor_revision += 1
            except RevisionConflict as error:
                return await self._terminal_failure(
                    command,
                    run,
                    "CURSOR_COMMIT_CONFLICT",
                    "cursor commit conflict",
                    "failed",
                    error,
                    event_id=event.event_id,
                    event_count=candidate_count,
                    replay_count=replay_count,
                )
            except Exception as error:  # noqa: BLE001 - source/evidence boundary is finite.
                try:
                    await asyncio.to_thread(
                        self._repository.complete_event,
                        project_id=command.project_id,
                        installation_id=command.installation_id,
                        event_id=event.event_id,
                        body_hash=event.canonical_body_hash.removeprefix("sha256:"),
                        outcome="failed",
                        checkpoint=None,
                        expected_cursor_revision=cursor_revision,
                    )
                except Exception as finalization_error:  # noqa: BLE001 - preserve the original terminal failure.
                    self._logger.error(
                        "connector event failure finalization failed; original failure remains terminal",
                        extra={"failureType": type(finalization_error).__name__},
                    )
                return await self._terminal_failure(
                    command,
                    run,
                    "SOURCE_COMMIT_FAILED",
                    "source commit failed",
                    "failed",
                    error,
                    event_id=event.event_id,
                    event_count=candidate_count,
                    replay_count=replay_count,
                )
        outcome: SyncOutcome = (
            "truncated"
            if pull_outcome == "truncated"
            else (
                "replayed"
                if candidates and replay_count == len(candidates)
                else ("empty" if not candidates else "succeeded")
            )
        )
        await asyncio.to_thread(
            self._repository.finish_run,
            project_id=command.project_id,
            installation_id=command.installation_id,
            run_id=run.run_id,
            outcome=(
                "truncated"
                if outcome == "truncated"
                else ("replayed" if outcome == "replayed" else "accepted")
            ),
            event_count=candidate_count,
            replay_count=replay_count,
        )
        result = SyncResult(
            runId=run.run_id, outcome=outcome, eventCount=len(candidates), replayCount=replay_count
        )
        self._emit_terminal(command, connector_type, result, run.started_at)
        await self._audit(
            command.project_id,
            command.installation_id,
            "run",
            result.outcome,
            "connector-kernel",
            command.run_id,
            run.revision + 1,
        )
        return result

    async def _put_evidence(
        self, command: SyncCommand, content: bytes, content_type: str, source_reference: str
    ) -> EvidenceReceipt:
        # The canonical-event digest is namespaced (``sha256:<hex>``), while
        # the evidence port stores the raw lowercase SHA-256 hex digest.
        digest = sha256_digest(content).removeprefix("sha256:")
        request = EvidencePutRequest(
            command.project_id, content_type, len(content), digest, source_reference
        )

        async def stream() -> AsyncIterable[bytes]:
            yield content

        remaining = _remaining_seconds(command.deadline)
        if remaining <= 0:
            raise TimeoutError
        return await asyncio.wait_for(
            self._evidence.put(request, stream()),
            timeout=min(remaining, self._budget.evidence_seconds),
        )

    async def _commit_source(
        self,
        source_committer: SourceCommitter,
        event: CanonicalEvent,
        receipt: EvidenceReceipt,
        deadline: datetime,
    ) -> None:
        remaining = _remaining_seconds(deadline)
        if remaining <= 0:
            raise TimeoutError
        await asyncio.wait_for(
            source_committer.commit_source(event, receipt),
            timeout=min(remaining, self._budget.semantic_core_seconds),
        )

    async def _terminal_failure(
        self,
        command: SyncCommand,
        run: SyncRunRecord,
        code: str,
        detail: str,
        outcome: SyncOutcome,
        error: BaseException | None,
        *,
        event_id: str | None = None,
        event_count: int = 0,
        replay_count: int = 0,
    ) -> SyncResult:
        safe_code = code if code in _ERROR_CODES else "ADAPTER_FAILED"
        safe = SanitizedConnectorError(
            code=cast(ErrorCode, safe_code),
            detail=detail,
            retryable=code
            in {
                "ADAPTER_UNAVAILABLE",
                "EVIDENCE_WRITE_FAILED",
                "SOURCE_COMMIT_FAILED",
                "CURSOR_COMMIT_CONFLICT",
            },
            correlationId=command.run_id,
            occurredAt=datetime.now(UTC),
        )
        dead_letter_id: int | None = None
        try:
            try:
                dead_letter_id = await asyncio.to_thread(
                    self._repository.record_dead_letter,
                    project_id=command.project_id,
                    installation_id=command.installation_id,
                    run_id=run.run_id,
                    event_id=event_id,
                    failure_code=safe.code,
                    sanitized_detail=safe.detail,
                )
            except Exception as dead_letter_error:  # noqa: BLE001 - preserve the safe terminal run outcome.
                self._logger.error(
                    "connector dead-letter persistence failed; terminal run outcome retained",
                    extra={"failureType": type(dead_letter_error).__name__},
                )
                dead_letter_id = None
        finally:
            await asyncio.to_thread(
                self._repository.finish_run,
                project_id=command.project_id,
                installation_id=command.installation_id,
                run_id=run.run_id,
                outcome="cancelled" if outcome in {"cancelled", "deadline-exceeded"} else "failed",
                failure_code=safe.code,
                failure_detail=safe.detail,
                event_count=event_count,
                replay_count=replay_count,
                dead_letter_id=dead_letter_id,
            )
        result = SyncResult(
            runId=run.run_id,
            outcome=outcome,
            eventCount=event_count,
            replayCount=replay_count,
            deadLetterId=dead_letter_id,
            failureCode=safe.code,
        )
        installation = self._repository.get_installation(command.project_id, command.installation_id)
        connector_type = installation.connector_type if installation is not None else "unknown"
        self._emit_terminal(command, connector_type, result, run.started_at)
        await self._audit(
            command.project_id,
            command.installation_id,
            "run",
            result.outcome,
            "connector-kernel",
            command.run_id,
            run.revision + 1,
        )
        return result

    def _emit_start(self, command: SyncCommand, connector_type: str) -> None:
        if self._telemetry is None:
            emit_safe(self._audit_sink, category="connector", action="connector.run", outcome="started", correlation_id=command.idempotency_key, project_id=command.project_id)
            return
        self._telemetry.emit(
            ConnectorTelemetryEvent(
                phase="start",
                operation="sync",
                connector_type=connector_type,
                project_scope=safe_project_scope(command.project_id),
                attempt_mode="explicit-retry" if command.retry else "single",
                outcome=None,
                duration_ms=None,
                event_count=0,
                replay_count=0,
                correlation_id=command.idempotency_key,
                recorded_at=now_utc(),
            )
        )
        emit_safe(self._audit_sink, category="connector", action="connector.run", outcome="started", correlation_id=command.idempotency_key, project_id=command.project_id)

    def _emit_terminal(
        self, command: SyncCommand, connector_type: str, result: SyncResult, started_at: datetime
    ) -> None:
        if self._telemetry is None:
            emit_safe(self._audit_sink, category="connector", action="connector.run", outcome=("succeeded" if result.outcome in {"succeeded", "empty", "replayed", "truncated"} else "failed"), correlation_id=command.idempotency_key, project_id=command.project_id)
            return
        duration = max(0, int((now_utc() - started_at).total_seconds() * 1000))
        self._telemetry.emit(
            ConnectorTelemetryEvent(
                phase="terminal",
                operation="sync",
                connector_type=connector_type,
                project_scope=safe_project_scope(command.project_id),
                attempt_mode="explicit-retry" if command.retry else "single",
                outcome=result.outcome,
                duration_ms=duration,
                event_count=result.event_count,
                replay_count=result.replay_count,
                correlation_id=command.idempotency_key,
                recorded_at=now_utc(),
            )
        )
        emit_safe(self._audit_sink, category="connector", action="connector.run", outcome=("succeeded" if result.outcome in {"succeeded", "empty", "replayed", "truncated"} else "failed"), correlation_id=command.idempotency_key, project_id=command.project_id)

    async def _audit(
        self,
        project_id: str,
        installation_id: str,
        operation: str,
        outcome: str,
        actor_reference: str,
        correlation_id: str,
        revision: int | None,
    ) -> None:
        try:
            await asyncio.to_thread(
                self._repository.record_audit,
                project_id=project_id,
                installation_id=installation_id,
                operation=operation,
                outcome=outcome,
                actor_reference=actor_reference,
                correlation_id=correlation_id,
                revision=revision,
            )
        except Exception:
            # Audit availability cannot convert a completed sync into a false failure.
            return


_ERROR_CODES = frozenset(
    {
        "ADAPTER_FAILED",
        "ADAPTER_OUTPUT_INVALID",
        "ADAPTER_CANCELLED",
        "ADAPTER_DEADLINE_EXCEEDED",
        "ADAPTER_LIMIT_EXCEEDED",
        "EVENT_OUTPUT_INVALID",
        "EVENT_IDEMPOTENCY_CONFLICT",
        "EVENT_BODY_CONFLICT",
        "CURSOR_COMMIT_CONFLICT",
        "EVIDENCE_WRITE_FAILED",
        "SOURCE_COMMIT_FAILED",
        "ADAPTER_CREDENTIAL_INVALID",
        "ADAPTER_PERMISSION_DENIED",
        "ADAPTER_PROVIDER_NOT_FOUND",
        "ADAPTER_UNAVAILABLE",
        "ADAPTER_RATE_LIMITED",
    }
)


def _remaining_seconds(deadline: datetime) -> float:
    return (deadline.astimezone(UTC) - datetime.now(UTC)).total_seconds()


def _pull_failure_code(outcome: SyncOutcome) -> str:
    return {
        "unavailable": "ADAPTER_UNAVAILABLE",
        "rate-limited": "ADAPTER_RATE_LIMITED",
        "deadline-exceeded": "ADAPTER_DEADLINE_EXCEEDED",
        "malformed-output": "ADAPTER_OUTPUT_INVALID",
        "cancelled": "ADAPTER_CANCELLED",
    }.get(outcome, "ADAPTER_FAILED")


def _fixture_reference(capability_snapshot: dict[str, object]) -> str:
    value = capability_snapshot.get("fixtureReference")
    if not isinstance(value, str):
        raise ValueError("ADAPTER_INSTALLATION_INVALID")
    return value
