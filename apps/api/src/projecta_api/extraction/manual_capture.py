"""Deterministically bind human Note candidates to server-owned source evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from projecta_api.extraction.source_version import SourceVersion, create_source_version
from projecta_api.extraction.text_anchor import (
    TextAnchor,
    TextAnchorVerificationError,
    resolve_text_anchor,
)
from projecta_api.structured_note import CandidateEditType


class ManualCaptureContextError(ValueError):
    """Raised when Core source context cannot be bound to an exact Note revision."""


class _CoreManualCaptureContext(BaseModel):
    """Finite private Core response accepted for a manually authored Note candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(alias="candidateId", pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    candidate_revision: int = Field(alias="candidateRevision", ge=1)
    candidate_status: Literal["extracted", "validated"] = Field(alias="candidateStatus")
    source_artifact_id: str = Field(
        alias="sourceArtifactId", pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
    )
    title: str = Field(min_length=1, max_length=512)
    raw_text: str = Field(alias="rawText", min_length=1)
    evidence_text: str = Field(alias="evidenceText", min_length=1)
    entity_type: CandidateEditType = Field(alias="entityType")
    start_offset: int = Field(alias="startOffset", ge=0)
    end_offset: int = Field(alias="endOffset", gt=0)


@dataclass(frozen=True, slots=True)
class VerifiedManualCapture:
    """Server-recomputed source version and exact Unicode anchor for a Note item."""

    candidate_revision: int
    candidate_status: Literal["extracted", "validated"]
    title: str
    source_version: SourceVersion
    source_text: str
    evidence_text: str
    entity_type: CandidateEditType
    anchor: TextAnchor


def resolve_manual_capture(project_id: str, payload: object) -> VerifiedManualCapture:
    """Validate Core's project-bound Note span and derive its immutable source anchor."""

    try:
        context = _CoreManualCaptureContext.model_validate(payload)
        source = create_source_version(
            project_id=project_id,
            source_artifact_id=context.source_artifact_id,
            content=context.raw_text,
        )
        if context.start_offset >= context.end_offset or context.end_offset > len(context.raw_text):
            raise ManualCaptureContextError("source anchor range is invalid")
        exact_quote = context.raw_text[context.start_offset : context.end_offset]
        if exact_quote != context.evidence_text:
            raise ManualCaptureContextError("source anchor does not match the Note occurrence")
        occurrence = _occurrence_at(context.raw_text, exact_quote, context.start_offset)
        anchor = resolve_text_anchor(
            source,
            context.raw_text,
            exact_quote,
            occurrence=occurrence,
            block_id=context.source_artifact_id,
        )
        if anchor.start_offset != context.start_offset or anchor.end_offset != context.end_offset:
            raise ManualCaptureContextError("source anchor does not match the Note occurrence")
    except (ValidationError, TextAnchorVerificationError, UnicodeError, ValueError) as error:
        raise ManualCaptureContextError("manual Note source context is invalid") from error
    return VerifiedManualCapture(
        candidate_revision=context.candidate_revision,
        title=context.title,
        candidate_status=context.candidate_status,
        source_version=source,
        source_text=context.raw_text,
        evidence_text=exact_quote,
        entity_type=context.entity_type,
        anchor=anchor,
    )


def _occurrence_at(text: str, quote: str, selected_offset: int) -> int:
    """Return the one-based overlapping occurrence containing the server span."""

    occurrence = 0
    cursor = 0
    while cursor <= len(text) - len(quote):
        index = text.find(quote, cursor)
        if index < 0:
            break
        occurrence += 1
        if index == selected_offset:
            return occurrence
        cursor = index + 1
    raise ManualCaptureContextError("source anchor occurrence is not present")
