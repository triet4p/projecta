"""Versioned M4 query, projection, citation, and answer contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

QueryId = Literal["current-requirements", "requirement-history", "unresolved-blockers"]
KnowledgeStatus = Literal["asserted", "inferred"]


class QueryIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_version: Literal["m4.v1"] = "m4.v1"
    query_id: QueryId = Field(alias="queryId")
    parameters: dict[str, str | int] = Field(default_factory=dict)


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    source_id: str = Field(alias="sourceId")
    evidence_text: str = Field(alias="evidenceText", min_length=1)
    start_offset: int = Field(alias="startOffset", ge=0)
    end_offset: int = Field(alias="endOffset", gt=0)


class Derivation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str = Field(alias="ruleId")
    rule_version: str = Field(alias="ruleVersion")
    input_ids: list[str] = Field(alias="inputIds")


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str
    label: str
    status: KnowledgeStatus
    as_of: datetime | None = Field(default=None, alias="asOf")
    citation_ids: list[str] = Field(default_factory=list, alias="citationIds")
    derivation: Derivation | None = None


class ProjectionMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    projection_version: Literal["m4.v1"] = Field(default="m4.v1", alias="projectionVersion")
    source_revision: str = Field(alias="sourceRevision")
    as_of: datetime = Field(alias="asOf")
    partial: bool = False
    stale: bool = False


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_version: Literal["m4.v1"] = Field(default="m4.v1", alias="answerVersion")
    query: QueryIntent
    text: str
    facts: list[Fact]
    citations: list[Citation]
    meta: ProjectionMeta
    complete: bool = True
    abstained: bool = False
    warnings: list[str] = Field(default_factory=list)
