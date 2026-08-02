"""M3 application orchestration from untyped note to Core ingestion."""

import logging
from time import monotonic
from typing import Protocol

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.contracts import EXTRACTION_SCHEMA_VERSION, ExtractionResponse
from projecta_api.extraction.normalize import normalize_extraction
from projecta_api.extraction.prompt import PROMPT_VERSION, build_extraction_prompt
from projecta_api.extraction.telemetry import ExtractionTelemetryEvent, emit_extraction_event
from projecta_api.llm.gateway import GatewayRequest, LLMGateway
from projecta_api.models import ExtractionRequest


class ExtractionPersistence(Protocol):
    async def entity_link_context(self, context: TrustedRequestContext, limit: int = 50) -> list[dict[str, str]]: ...
    async def ingest_extraction(self, context: TrustedRequestContext, key: str, body: object) -> object: ...


class ExtractionOrchestrator:
    """Keep gateway, normalization, project read, and semantic mutation ordered."""

    def __init__(self, gateway: LLMGateway, semantic: ExtractionPersistence, model_id: str | None, logger: logging.Logger | None = None, timeout_seconds: float = 60.0) -> None:
        self._gateway = gateway
        self._semantic = semantic
        self._model_id = model_id
        self._logger = logger or logging.getLogger(__name__)
        self._timeout_seconds = timeout_seconds

    async def extract(self, context: TrustedRequestContext, key: str, request: ExtractionRequest) -> object:
        started = monotonic()
        if not self._model_id:
            from projecta_api.llm.gateway import NormalizedGatewayError

            raise NormalizedGatewayError("configuration_invalid", "LLM model is not configured", retryable=False)
        bounded = await self._semantic.entity_link_context(context)
        system, user = build_extraction_prompt(
            request.raw_text,
            ["Requirement", "Decision", "Question", "Task", "Risk", "Assumption", "Constraint", "ProgressClaim", "ResearchFinding"],
            ["implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy"],
            bounded,
        )
        try:
            gateway_result = await self._gateway.extract(
                GatewayRequest(
                    schemaVersion=EXTRACTION_SCHEMA_VERSION,
                    modelId=self._model_id,
                    systemPrompt=system,
                    userPrompt=user,
                    responseSchema=_response_schema(),
                    timeoutSeconds=self._timeout_seconds,
                )
            )
            normalized = normalize_extraction(request.raw_text, gateway_result.extraction, bounded)
            body = _ingestion_body(request.raw_text, normalized)
            result = await self._semantic.ingest_extraction(context, key, body)
            usage = gateway_result.usage
            emit_extraction_event(self._logger, ExtractionTelemetryEvent(
                event="extraction.completed", requestId=context.request_id, provider="deepseek-responses",
                modelVersion=normalized.model_version, promptVersion=PROMPT_VERSION,
                schemaVersion=normalized.schema_version, latencyMs=int((monotonic() - started) * 1000),
                inputTokens=usage.input_tokens if usage else None, outputTokens=usage.output_tokens if usage else None,
                entityCount=len(normalized.entities), relationCount=len(normalized.relations), linkCount=len(normalized.links),
            ))
            return result
        except Exception as exc:
            error_class = getattr(exc, "error_class", "normalization_invalid")
            emit_extraction_event(self._logger, ExtractionTelemetryEvent(
                event="extraction.failed", requestId=context.request_id, provider="deepseek-responses",
                modelVersion=self._model_id or "unconfigured", promptVersion=PROMPT_VERSION,
                schemaVersion=EXTRACTION_SCHEMA_VERSION, latencyMs=int((monotonic() - started) * 1000),
                errorClass=str(error_class),
            ))
            raise


def _response_schema() -> dict[str, object]:
    """Return a DeepSeek-compatible strict schema with every object field required."""
    evidence = {
        "type": "object",
        "properties": {"startOffset": {"type": "integer"}, "endOffset": {"type": "integer"}, "text": {"type": "string"}},
        "required": ["startOffset", "endOffset", "text"],
        "additionalProperties": False,
    }
    entity = {
        "type": "object",
        "properties": {"type": {"type": "string", "enum": ["Requirement", "Decision", "Question", "Task", "Risk", "Assumption", "Constraint", "ProgressClaim", "ResearchFinding"]}, "label": {"type": "string"}, "evidence": evidence, "confidence": {"type": "number"}},
        "required": ["type", "label", "evidence", "confidence"], "additionalProperties": False,
    }
    relation = {
        "type": "object",
        "properties": {"predicate": {"type": "string", "enum": ["implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy"]}, "sourceEntityId": {"type": "string"}, "targetEntityId": {"type": "string"}, "evidence": evidence, "confidence": {"type": "number"}},
        "required": ["predicate", "sourceEntityId", "targetEntityId", "evidence", "confidence"], "additionalProperties": False,
    }
    link = {
        "type": "object",
        "properties": {"mention": {"type": "string"}, "targetEntityId": {"type": "string"}, "evidence": evidence, "confidence": {"type": "number"}},
        "required": ["mention", "targetEntityId", "evidence", "confidence"], "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"entities": {"type": "array", "items": entity}, "relations": {"type": "array", "items": relation}, "links": {"type": "array", "items": link}, "abstentionReason": {"type": ["string", "null"]}},
        "required": ["entities", "relations", "links", "abstentionReason"],
        "additionalProperties": False,
    }


def _ingestion_body(raw_text: str, response: ExtractionResponse) -> dict[str, object]:
    data = response.model_dump(mode="json", by_alias=True)
    entities = [
        {
            "type": item["type"],
            "label": item["label"],
            "text": item["evidence"]["text"],
            "startOffset": item["evidence"]["startOffset"],
            "endOffset": item["evidence"]["endOffset"],
            "confidence": float(item["confidence"]),
        }
        for item in data["entities"]
    ]
    relations = [
        {"predicate": item["predicate"], "sourceEntityId": item["sourceEntityId"], "targetEntityId": item["targetEntityId"], "text": item["evidence"]["text"], "startOffset": item["evidence"]["startOffset"], "endOffset": item["evidence"]["endOffset"], "confidence": float(item["confidence"])}
        for item in data["relations"]
    ]
    links = [
        {"mention": item["mention"], "targetEntityId": item["targetEntityId"], "startOffset": item["evidence"]["startOffset"], "endOffset": item["evidence"]["endOffset"], "confidence": float(item["confidence"])}
        for item in data["links"]
    ]
    return {
        "rawText": raw_text,
        "modelId": data["modelId"],
        "modelVersion": data["modelVersion"],
        "promptVersion": PROMPT_VERSION,
        "schemaVersion": data["schemaVersion"],
        "entities": entities,
        "relations": relations,
        "links": links,
        "abstentionReason": data.get("abstentionReason"),
    }
