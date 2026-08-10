"""Strict M3 extraction contracts shared by replay and live adapters.

The contract intentionally contains domain-safe enums and opaque IDs only. It
does not permit RDF, graph names, SPARQL, provider SDK objects, or arbitrary
IRIs to cross the gateway boundary.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

EXTRACTION_SCHEMA_VERSION = "m3.v1"

EntityType = Literal[
    "Requirement",
    "Decision",
    "Question",
    "Task",
    "Risk",
    "Assumption",
    "Constraint",
    "ProgressClaim",
    "ResearchFinding",
]
RelationPredicate = Literal[
    "implements",
    "blocks",
    "dependsOn",
    "supports",
    "answers",
    "resolves",
    "constrainedBy",
]
OpaqueId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
Version = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]


class ContractModel(BaseModel):
    """Common strict model configuration for untrusted structured output."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class EvidenceSpan(ContractModel):
    """Exact half-open Unicode-code-point evidence range in the source note."""

    start_offset: int = Field(ge=0, alias="startOffset")
    end_offset: int = Field(gt=0, alias="endOffset")
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_non_empty_range(self) -> "EvidenceSpan":
        if self.start_offset >= self.end_offset:
            raise ValueError("evidence range must be non-empty and half-open")
        return self


class EntityCandidateOutput(ContractModel):
    """A proposed typed entity mention; target IDs are not generated here."""

    type: EntityType
    label: str = Field(min_length=1, max_length=4096)
    evidence: EvidenceSpan
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class RelationCandidateOutput(ContractModel):
    """A proposed allowlisted relation between opaque entity references."""

    predicate: RelationPredicate
    source_entity_id: OpaqueId = Field(alias="sourceEntityId")
    target_entity_id: OpaqueId = Field(alias="targetEntityId")
    evidence: EvidenceSpan
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class EntityLinkCandidateOutput(ContractModel):
    """A proposed link to an opaque existing ID, later checked against context."""

    mention: str = Field(min_length=1, max_length=4096)
    target_entity_id: OpaqueId = Field(alias="targetEntityId")
    evidence: EvidenceSpan
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class UsageMetadata(ContractModel):
    """Provider-neutral usage counters; all fields are optional and non-negative."""

    input_tokens: int | None = Field(default=None, ge=0, alias="inputTokens")
    output_tokens: int | None = Field(default=None, ge=0, alias="outputTokens")
    total_tokens: int | None = Field(default=None, ge=0, alias="totalTokens")
    reasoning_tokens: int | None = Field(default=None, ge=0, alias="reasoningTokens")


class ExtractionResponse(ContractModel):
    """Versioned structured output accepted from replay or a live adapter."""

    schema_version: Literal["m3.v1"] = Field(alias="schemaVersion")
    model_id: Version = Field(alias="modelId")
    model_version: Version = Field(alias="modelVersion")
    entities: list[EntityCandidateOutput] = Field(default_factory=list[EntityCandidateOutput])
    relations: list[RelationCandidateOutput] = Field(default_factory=list[RelationCandidateOutput])
    links: list[EntityLinkCandidateOutput] = Field(default_factory=list[EntityLinkCandidateOutput])
    abstention_reason: str | None = Field(
        default=None, min_length=1, max_length=1024, alias="abstentionReason"
    )
    usage: UsageMetadata | None = None

    @model_validator(mode="after")
    def validate_abstention(self) -> "ExtractionResponse":
        if self.abstention_reason and (self.entities or self.relations or self.links):
            raise ValueError("abstention cannot be combined with extraction candidates")
        if not self.abstention_reason and not (self.entities or self.relations or self.links):
            raise ValueError("an empty extraction requires an abstention reason")
        return self
