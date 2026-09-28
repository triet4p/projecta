"""M3 application orchestration from untyped note to Core ingestion."""

import logging
from collections.abc import Callable, Sequence
from time import monotonic
from typing import Literal, Protocol, cast

from projecta_api.configuration.models import LLMConfigurationSnapshot
from projecta_api.configuration.ports import RuntimeConfigurationProvider
from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.confirmed_entity_gate import (
    ConfirmedEntityRegistry,
    EntityHandle,
    RelationAuthorization,
    RelationRequest,
)
from projecta_api.extraction.constrained_relation import (
    ConstrainedRelationRequest,
    ConstrainedRelationResult,
    constrain_relation,
)
from projecta_api.extraction.contracts import (
    EXTRACTION_SCHEMA_VERSION,
    EXTRACTION_SCHEMA_VERSION_V2,
    ExtractionResponse,
    UsageMetadata,
)
from projecta_api.extraction.authoring_telemetry import AuthoringTelemetryService
from projecta_api.extraction.correction_burden import (
    CorrectionBurdenEventRecord,
    CorrectionBurdenRequest,
    CorrectionBurdenTelemetryService,
    LifecycleOutcome,
)
from projecta_api.extraction.item_validation import (
    ItemValidationBatch,
    ItemValidationResult,
    validate_item_batch,
)
from projecta_api.extraction.normalize import normalize_extraction
from projecta_api.extraction.prompt import PROMPT_VERSION, build_extraction_prompt
from projecta_api.extraction.relation_evidence_selection import (
    RelationEvidenceSelection,
    SourceBlock,
    select_relation_evidence,
)
from projecta_api.extraction.review_receipts import (
    ReviewActorContext,
    ReviewDecisionReceiptRecord,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
)
from projecta_api.extraction.source_version import (
    RetentionMetadata,
    SourceVersion,
    create_source_version,
)
from projecta_api.extraction.telemetry import ExtractionTelemetryEvent, emit_extraction_event
from projecta_api.extraction.text_anchor import (
    TextAnchor,
    TextAnchorVerificationError,
    resolve_text_anchor,
)
from projecta_api.llm.gateway import GatewayRequest, LLMGateway
from projecta_api.models import ExtractionRequest


class ExtractionPersistence(Protocol):
    async def entity_link_context(
        self, context: TrustedRequestContext, limit: int = 50
    ) -> list[dict[str, str]]: ...
    async def ingest_extraction(
        self, context: TrustedRequestContext, key: str, body: object
    ) -> object: ...


class ExtractionOrchestrator:
    """Keep gateway, normalization, project read, and semantic mutation ordered."""

    _schema_version: Literal["m3.v1", "m3.v2"]

    def __init__(
        self,
        gateway: LLMGateway | None,
        semantic: ExtractionPersistence,
        model_id: str | None,
        logger: logging.Logger | None = None,
        timeout_seconds: float = 60.0,
        configuration_provider: RuntimeConfigurationProvider | None = None,
        gateway_factory: Callable[[LLMConfigurationSnapshot], LLMGateway] | None = None,
        schema_version: str = EXTRACTION_SCHEMA_VERSION,
        review_receipt_service: ReviewDecisionReceiptService | None = None,
        correction_burden_service: CorrectionBurdenTelemetryService | None = None,
        authoring_telemetry_service: AuthoringTelemetryService | None = None,
    ) -> None:
        self._gateway = gateway
        self._semantic = semantic
        self._model_id = model_id
        self._logger = logger or logging.getLogger(__name__)
        self._timeout_seconds = timeout_seconds
        self._configuration_provider = configuration_provider
        self._gateway_factory = gateway_factory
        if schema_version not in {EXTRACTION_SCHEMA_VERSION, EXTRACTION_SCHEMA_VERSION_V2}:
            raise ValueError(f"unsupported extraction schema version: {schema_version}")
        self._schema_version = cast(Literal["m3.v1", "m3.v2"], schema_version)
        self._review_receipt_service = review_receipt_service
        self._correction_burden_service = correction_burden_service
        self._authoring_telemetry_service = authoring_telemetry_service

    async def propose(
        self, context: TrustedRequestContext, request: ExtractionRequest
    ) -> ExtractionResponse:
        """Return normalized proposals without writing source or candidate graphs."""

        started = monotonic()
        model_id = self._model_id or "unconfigured"
        try:
            normalized, usage, model_id = await self._normalize(
                context, request, proposal_only=True
            )
            self._emit_completed(context, normalized, usage, started)
            return normalized
        except Exception as exc:
            self._emit_failed(context, model_id, exc, started)
            raise

    def create_source_version(
        self,
        context: TrustedRequestContext,
        source_artifact_id: str,
        content: bytes | str,
        *,
        parent_source_version_id: str | None = None,
        parent_canonical_content_digest: str | None = None,
        retention: RetentionMetadata | None = None,
    ) -> SourceVersion:
        """Create an opt-in immutable source receipt for this project context."""

        return create_source_version(
            project_id=context.project_id,
            source_artifact_id=source_artifact_id,
            content=content,
            parent_source_version_id=parent_source_version_id,
            parent_canonical_content_digest=parent_canonical_content_digest,
            retention=retention,
        )

    def resolve_text_anchor(
        self,
        context: TrustedRequestContext,
        source: SourceVersion | None,
        content: bytes | str | None,
        exact_quote: str,
        *,
        occurrence: int | None = None,
        block_id: str | None = None,
    ) -> TextAnchor:
        """Resolve an opt-in source-bound anchor without changing legacy extraction."""

        if source is None or source.project_id != context.project_id:
            raise TextAnchorVerificationError("SOURCE_VERSION_MISMATCH")
        return resolve_text_anchor(
            source,
            content,
            exact_quote,
            occurrence=occurrence,
            block_id=block_id,
        )

    def validate_items(
        self,
        context: TrustedRequestContext,
        source: SourceVersion | None,
        content: bytes | str | None,
        items: list[object],
    ) -> ItemValidationBatch:
        """Classify extraction items through the explicit RM-57 opt-in boundary."""

        return validate_item_batch(context.project_id, source, content, items)

    def confirm_entity(
        self,
        context: TrustedRequestContext,
        registry: ConfirmedEntityRegistry,
        source: SourceVersion | None,
        validation: ItemValidationResult,
        entity_type: str,
        candidate_key: str,
        *,
        confirmation_revision: str,
        review_confirmed: bool = False,
    ) -> EntityHandle:
        """Issue a server-owned handle through the explicit RM-58 opt-in boundary."""

        return registry.issue_entity_handle(
            context.project_id,
            source,
            validation,
            entity_type,
            candidate_key,
            confirmation_revision=confirmation_revision,
            review_confirmed=review_confirmed,
        )

    def authorize_relation(
        self,
        context: TrustedRequestContext,
        registry: ConfirmedEntityRegistry,
        source: SourceVersion | None,
        request: RelationRequest,
    ) -> RelationAuthorization:
        """Authorize a relation only after server-side resolution of both handles."""

        return registry.authorize_relation(context.project_id, source, request)

    def select_relation_evidence(
        self,
        context: TrustedRequestContext,
        source: SourceVersion | None,
        content: bytes | str | None,
        authorization: RelationAuthorization | None,
        source_anchor: TextAnchor | None,
        target_anchor: TextAnchor | None,
        *,
        trigger_anchor: TextAnchor | None = None,
        trigger_required: bool = False,
        server_blocks: list[SourceBlock] | None = None,
    ) -> RelationEvidenceSelection:
        """Select source-owned relation evidence through the explicit RM-59 opt-in."""

        return select_relation_evidence(
            context.project_id,
            source,
            content,
            authorization,
            source_anchor,
            target_anchor,
            trigger_anchor=trigger_anchor,
            trigger_required=trigger_required,
            server_blocks=server_blocks,
        )

    def constrain_relation(
        self,
        context: TrustedRequestContext,
        source: SourceVersion | None,
        request: ConstrainedRelationRequest,
    ) -> ConstrainedRelationResult:
        """Validate constrained semantics through the explicit RM-60 opt-in."""

        return constrain_relation(context.project_id, source, request)

    def record_review_decision(
        self,
        context: TrustedRequestContext,
        actor: ReviewActorContext,
        request: ReviewDecisionRequest,
    ) -> ReviewDecisionReceiptRecord:
        """Persist an explicit reviewer action through the opt-in RM-61 boundary."""

        if self._review_receipt_service is None:
            raise RuntimeError("review receipt persistence is unavailable")
        if actor.project_id != context.project_id:
            raise ValueError("review actor project does not match trusted context")
        receipt = self._review_receipt_service.record(actor, request)
        if self._correction_burden_service is not None:
            try:
                outcome = cast(LifecycleOutcome, {
                    "confirm": "confirmed",
                    "edit": "edited",
                    "reject": "rejected",
                    "abstain": "abstained",
                }[request.decision])
                self._correction_burden_service.record(
                    CorrectionBurdenRequest(
                        projectId=request.project_id,
                        itemKind=request.item_kind,
                        itemId=request.item_handle,
                        assertionId=request.item_handle,
                        sourceVersionId=request.source_version_id,
                        sourceVersionRevision=request.source_version_revision,
                        reviewReceiptDigest=receipt.receipt_digest,
                        correctionCategory="minor" if request.decision == "edit" else "unchanged",
                        correctionDimensions=(),
                        reviewOutcome=outcome,
                        semanticEditCount=1 if request.decision == "edit" else 0,
                        reviewLatencyMs=0,
                        materializationState="not-materialized",
                        inferenceState="not-materialized",
                        idempotencyKey="review-" + receipt.idempotency_digest,
                    )
                )
            except Exception as error:  # telemetry is an explicit, non-provider side hook
                self._logger.warning("correction-burden review hook failed safely: %s", type(error).__name__)
        return receipt

    def record_correction_burden(
        self, context: TrustedRequestContext, request: CorrectionBurdenRequest
    ) -> CorrectionBurdenEventRecord:
        """Explicit lifecycle hook for materialization/inference boundary callers."""

        if context.project_id != request.project_id:
            raise ValueError("telemetry project does not match trusted context")
        if self._correction_burden_service is None:
            raise RuntimeError("correction-burden telemetry persistence is unavailable")
        event = self._correction_burden_service.record(request)
        if (
            event.materialization_state == "accepted"
            and self._authoring_telemetry_service is not None
        ):
            try:
                self._authoring_telemetry_service.record_accepted_assertion(
                    context.project_id, context.actor_id, event
                )
            except Exception as error:
                self._logger.warning(
                    "authoring telemetry accepted-assertion hook failed safely: %s",
                    type(error).__name__,
                )
        return event

    def review_decision_history(
        self,
        context: TrustedRequestContext,
        actor: ReviewActorContext,
        item_kind: Literal["entity", "relation"],
        item_handle: str,
    ) -> Sequence[ReviewDecisionReceiptRecord]:
        """Read the append-only receipt state for a trusted workbench item."""

        if self._review_receipt_service is None:
            raise RuntimeError("review receipt persistence is unavailable")
        if actor.project_id != context.project_id:
            raise ValueError("review actor project does not match trusted context")
        return self._review_receipt_service.history(actor, item_kind, item_handle)

    async def extract(
        self, context: TrustedRequestContext, key: str, request: ExtractionRequest
    ) -> object:
        started = monotonic()
        model_id = self._model_id or "unconfigured"
        try:
            normalized, usage, model_id = await self._normalize(context, request)
            body = _ingestion_body(request.raw_text, normalized)
            result = await self._semantic.ingest_extraction(context, key, body)
            result = _with_extraction_details(result, normalized)
            self._emit_completed(context, normalized, usage, started)
            return result
        except Exception as exc:
            self._emit_failed(context, model_id, exc, started)
            raise

    async def _normalize(
        self,
        context: TrustedRequestContext,
        request: ExtractionRequest,
        *,
        proposal_only: bool = False,
    ) -> tuple[ExtractionResponse, UsageMetadata | None, str]:
        operation_gateway = self._gateway
        model_id = self._model_id
        profile_revision = "injected"
        if self._configuration_provider is not None and self._gateway_factory is not None:
            snapshot = self._configuration_provider.resolve_llm(context)
            operation_gateway = self._gateway_factory(snapshot)
            model_id = snapshot.model
            profile_revision = snapshot.revision
        if operation_gateway is None or not model_id:
            from projecta_api.llm.gateway import NormalizedGatewayError

            raise NormalizedGatewayError(
                "configuration_invalid", "LLM model is not configured", retryable=False
            )
        bounded = [] if proposal_only else await self._semantic.entity_link_context(context)
        system, user = build_extraction_prompt(
            request.raw_text,
            [
                "Requirement",
                "Decision",
                "Question",
                "Task",
                "Risk",
                "Assumption",
                "Constraint",
                "ProgressClaim",
                "ResearchFinding",
            ],
            (
                []
                if proposal_only
                else [
                    "implements",
                    "blocks",
                    "dependsOn",
                    "supports",
                    "answers",
                    "resolves",
                    "constrainedBy",
                ]
            ),
            bounded,
            schema_version=self._schema_version,
        )
        if self._schema_version == EXTRACTION_SCHEMA_VERSION_V2:
            user += (
                "\nContract m3.v2: assign every emitted entity a unique local "
                "candidateId. Relation sourceEntityId and targetEntityId may "
                "reference those local candidate IDs or bounded same-project IDs. "
                "For every entity, relation and link evidence, return exact text "
                "and its one-based occurrence in the whole note; do not return "
                "offsets. The server materializes offsets."
            )
        if proposal_only:
            user += (
                "\nAssisted import mode: return only entity proposals and an "
                "abstention reason. Relations and links are not representable "
                "in the Note composer and must not be emitted. For each evidence "
                "object, quote exact source text and return its one-based occurrence "
                "number in the whole note. The server derives offsets; do not return "
                "startOffset or endOffset."
            )
        gateway_result = await operation_gateway.extract(
            GatewayRequest(
                schemaVersion=self._schema_version,
                modelId=model_id,
                systemPrompt=system,
                userPrompt=user,
                responseSchema=_response_schema(
                    schema_version=self._schema_version, proposal_only=proposal_only
                ),
                sourceText=request.raw_text,
                timeoutSeconds=self._timeout_seconds,
                maxOutputTokens=4_096,
                requestId=context.request_id,
                operationId=context.operation_id,
                profileRevision=profile_revision,
            )
        )
        normalized = normalize_extraction(request.raw_text, gateway_result.extraction, bounded)
        return normalized, gateway_result.usage, model_id

    def _emit_completed(
        self,
        context: TrustedRequestContext,
        normalized: ExtractionResponse,
        usage: UsageMetadata | None,
        started: float,
    ) -> None:
        emit_extraction_event(
            self._logger,
            ExtractionTelemetryEvent(
                event="extraction.completed",
                requestId=context.request_id,
                provider="deepseek-responses",
                modelVersion=normalized.model_version,
                promptVersion=PROMPT_VERSION,
                schemaVersion=normalized.schema_version,
                latencyMs=int((monotonic() - started) * 1000),
                inputTokens=usage.input_tokens if usage else None,
                promptCacheHitTokens=(
                    usage.prompt_cache_hit_tokens if usage else None
                ),
                promptCacheMissTokens=(
                    usage.prompt_cache_miss_tokens if usage else None
                ),
                outputTokens=usage.output_tokens if usage else None,
                reasoningTokens=usage.reasoning_tokens if usage else None,
                entityCount=len(normalized.entities),
                relationCount=len(normalized.relations),
                linkCount=len(normalized.links),
            ),
        )

    def _emit_failed(
        self,
        context: TrustedRequestContext,
        model_id: str,
        error: Exception,
        started: float,
    ) -> None:
        error_class = getattr(error, "error_class", "normalization_invalid")
        emit_extraction_event(
            self._logger,
            ExtractionTelemetryEvent(
                event="extraction.failed",
                requestId=context.request_id,
                provider="deepseek-responses",
                modelVersion=model_id,
                promptVersion=PROMPT_VERSION,
                schemaVersion=EXTRACTION_SCHEMA_VERSION,
                latencyMs=int((monotonic() - started) * 1000),
                errorClass=str(error_class),
            ),
        )


def _response_schema(
    *, schema_version: str = EXTRACTION_SCHEMA_VERSION, proposal_only: bool = False
) -> dict[str, object]:
    """Return a DeepSeek-compatible strict schema with every object field required."""
    evidence_properties: dict[str, object]
    evidence_required: list[str]
    if schema_version == EXTRACTION_SCHEMA_VERSION_V2 or proposal_only:
        evidence_properties = {
            "text": {"type": "string"},
            "occurrence": {"type": "integer", "minimum": 1},
        }
        evidence_required = ["text", "occurrence"]
    else:
        evidence_properties = {
            "startOffset": {"type": "integer"},
            "endOffset": {"type": "integer"},
            "text": {"type": "string"},
        }
        evidence_required = ["startOffset", "endOffset", "text"]
    evidence = {
        "type": "object",
        "properties": evidence_properties,
        "required": evidence_required,
        "additionalProperties": False,
    }
    entity = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "Requirement",
                    "Decision",
                    "Question",
                    "Task",
                    "Risk",
                    "Assumption",
                    "Constraint",
                    "ProgressClaim",
                    "ResearchFinding",
                ],
            },
            **(
                {"candidateId": {"type": "string"}}
                if schema_version == EXTRACTION_SCHEMA_VERSION_V2
                else {}
            ),
            "label": {"type": "string"},
            "evidence": evidence,
            "confidence": {"type": "number"},
        },
        "required": [
            *(["candidateId"] if schema_version == EXTRACTION_SCHEMA_VERSION_V2 else []),
            "type",
            "label",
            "evidence",
            "confidence",
        ],
        "additionalProperties": False,
    }
    relation = {
        "type": "object",
        "properties": {
            "predicate": {
                "type": "string",
                "enum": [
                    "implements",
                    "blocks",
                    "dependsOn",
                    "supports",
                    "answers",
                    "resolves",
                    "constrainedBy",
                ],
            },
            "sourceEntityId": {"type": "string"},
            "targetEntityId": {"type": "string"},
            "evidence": evidence,
            "confidence": {"type": "number"},
        },
        "required": ["predicate", "sourceEntityId", "targetEntityId", "evidence", "confidence"],
        "additionalProperties": False,
    }
    link = {
        "type": "object",
        "properties": {
            "mention": {"type": "string"},
            "targetEntityId": {"type": "string"},
            "evidence": evidence,
            "confidence": {"type": "number"},
        },
        "required": ["mention", "targetEntityId", "evidence", "confidence"],
        "additionalProperties": False,
    }
    properties: dict[str, object] = {
        "entities": {"type": "array", "items": entity},
        "abstentionReason": {"type": ["string", "null"]},
    }
    required = ["entities", "abstentionReason"]
    if not proposal_only:
        properties.update(
            {
                "relations": {"type": "array", "items": relation},
                "links": {"type": "array", "items": link},
            }
        )
        required = ["entities", "relations", "links", "abstentionReason"]
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _with_extraction_details(result: object, response: ExtractionResponse) -> object:
    """Expose normalized M3 details alongside opaque lifecycle identifiers."""
    if not isinstance(result, dict):
        return result
    raw_result = cast(dict[object, object], result)
    public_result: dict[str, object] = {str(key): value for key, value in raw_result.items()}
    normalized = response.model_dump(mode="json", by_alias=True)
    public_result.update(
        {
            "entities": normalized["entities"],
            "relations": normalized["relations"],
            "links": normalized["links"],
            "abstentionReason": normalized.get("abstentionReason"),
        }
    )
    return public_result


def _ingestion_body(raw_text: str, response: ExtractionResponse) -> dict[str, object]:
    entities: list[dict[str, object]] = []
    for item in response.entities:
        entity: dict[str, object] = {
            "type": item.type,
            "label": item.label,
            "text": item.evidence.text,
            "startOffset": item.evidence.start_offset,
            "endOffset": item.evidence.end_offset,
            "confidence": float(item.confidence),
        }
        if item.candidate_id is not None:
            entity["candidateId"] = item.candidate_id
        entities.append(entity)
    relations: list[dict[str, object]] = [
        {
            "predicate": item.predicate,
            "sourceEntityId": item.source_entity_id,
            "targetEntityId": item.target_entity_id,
            "text": item.evidence.text,
            "startOffset": item.evidence.start_offset,
            "endOffset": item.evidence.end_offset,
            "confidence": float(item.confidence),
        }
        for item in response.relations
    ]
    links: list[dict[str, object]] = [
        {
            "mention": item.mention,
            "targetEntityId": item.target_entity_id,
            "startOffset": item.evidence.start_offset,
            "endOffset": item.evidence.end_offset,
            "confidence": float(item.confidence),
        }
        for item in response.links
    ]
    return {
        "rawText": raw_text,
        "modelId": response.model_id,
        "modelVersion": response.model_version,
        "promptVersion": PROMPT_VERSION,
        "schemaVersion": response.schema_version,
        "entities": entities,
        "relations": relations,
        "links": links,
        "abstentionReason": response.abstention_reason,
    }
