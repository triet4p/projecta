"""Versioned trigger-aware envelope for the next relation-evidence tool."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from projecta_api.extraction.contracts import (
    ContractModel,
    ExtractionResponse,
    OpaqueId,
    RelationPredicate,
)
from projecta_api.extraction.relation_evidence import (
    RelationEvidenceRequest,
    materialize_relation_evidence,
)

RELATION_EVIDENCE_ENVELOPE_VERSION = "relation-evidence-envelope.v1"


class RelationTriggerV1(ContractModel):
    """A trigger quote bound to one relation's local endpoints."""

    predicate: RelationPredicate
    source_entity_id: OpaqueId = Field(alias="sourceEntityId")
    target_entity_id: OpaqueId = Field(alias="targetEntityId")
    trigger_quote: str = Field(min_length=1, alias="triggerQuote")


class RelationEvidenceEnvelopeV1(ContractModel):
    """M3 response plus required trigger context for relation post-processing."""

    schema_version: Literal["relation-evidence-envelope.v1"] = Field(
        default=RELATION_EVIDENCE_ENVELOPE_VERSION, alias="schemaVersion"
    )
    extraction: ExtractionResponse
    relation_triggers: list[RelationTriggerV1] = Field(
        default_factory=list, alias="relationTriggers"
    )

    @model_validator(mode="after")
    def require_trigger_for_each_relation(self) -> RelationEvidenceEnvelopeV1:
        expected = {
            (
                relation.predicate,
                relation.source_entity_id,
                relation.target_entity_id,
            )
            for relation in self.extraction.relations
        }
        actual = {
            (trigger.predicate, trigger.source_entity_id, trigger.target_entity_id)
            for trigger in self.relation_triggers
        }
        if len(actual) != len(self.relation_triggers):
            raise ValueError("relation trigger bindings must be unique")
        if actual != expected:
            raise ValueError(
                "relation evidence envelope requires one triggerQuote per relation"
            )
        return self


def materialize_relation_evidence_envelope(
    raw_text: str, envelope: RelationEvidenceEnvelopeV1
) -> ExtractionResponse | None:
    """Materialize every trigger-bound relation, dropping invalid ones."""

    entity_spans = {
        str(entity.candidate_id): entity.evidence
        for entity in envelope.extraction.entities
        if entity.candidate_id is not None
    }
    triggers = {
        (
            trigger.predicate,
            trigger.source_entity_id,
            trigger.target_entity_id,
        ): trigger.trigger_quote
        for trigger in envelope.relation_triggers
    }
    materialized = []
    for relation in envelope.extraction.relations:
        source_span = entity_spans.get(relation.source_entity_id)
        target_span = entity_spans.get(relation.target_entity_id)
        trigger_quote = triggers.get(
            (relation.predicate, relation.source_entity_id, relation.target_entity_id)
        )
        if source_span is None or target_span is None or trigger_quote is None:
            continue
        evidence = materialize_relation_evidence(
            raw_text,
            RelationEvidenceRequest(
                predicate=relation.predicate,
                source_entity_id=relation.source_entity_id,
                target_entity_id=relation.target_entity_id,
                source_span=source_span,
                target_span=target_span,
                trigger_quote=trigger_quote,
                trigger_required=True,
            ),
        )
        if evidence is not None:
            materialized.append(relation.model_copy(update={"evidence": evidence}))
    try:
        return envelope.extraction.model_copy(update={"relations": materialized})
    except ValueError:
        return None
