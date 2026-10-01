"""Canonical API schemas for the Manual Quick Note slice."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NoteItemType = Literal[
    "requirement",
    "decision",
    "question",
    "task",
    "risk",
    "assumption",
    "constraint",
    "progress-update",
    "research-need",
]


class TypedSegment(BaseModel):
    """One human-selected, exact source span."""

    model_config = ConfigDict(extra="forbid")
    type: NoteItemType
    start_offset: int = Field(ge=0, alias="startOffset")
    end_offset: int = Field(gt=0, alias="endOffset")
    text: str = Field(min_length=1)


class CaptureRequest(BaseModel):
    """Public manual capture input after canonical line-ending normalization."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Quick Note", min_length=1, max_length=512)
    raw_text: str = Field(min_length=1, alias="rawText")
    segments: list[TypedSegment] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> "CaptureRequest":
        """Require ordered, non-overlapping exact Unicode-code-point spans."""
        normalized = self.raw_text.replace("\r\n", "\n").replace("\r", "\n")
        previous_end = 0
        for segment in self.segments:
            if segment.start_offset < previous_end or segment.start_offset >= segment.end_offset:
                raise ValueError("segments must be ordered, non-overlapping, and non-empty")
            if segment.end_offset > len(normalized):
                raise ValueError("segment range is outside rawText")
            if normalized[segment.start_offset : segment.end_offset] != segment.text:
                raise ValueError("segment text must equal its rawText range")
            previous_end = segment.end_offset
        self.raw_text = normalized
        return self


class SemanticCaptureRequest(CaptureRequest):
    """Private server-authored capture metadata sent only to Semantic Core."""

    source_kind: Literal["manual", "text-import", "connector"] = Field(
        default="manual", alias="sourceKind"
    )
    source_content_hash: str | None = Field(
        default=None,
        alias="sourceContentHash",
        pattern=r"^sha256:[0-9a-f]{64}$",
    )


class ExtractionRequest(BaseModel):
    """Untyped Quick Note input for M3 extraction."""

    model_config = ConfigDict(extra="forbid")
    raw_text: str = Field(min_length=1, alias="rawText")
    extraction_version: Literal["m3.v1"] = Field(default="m3.v1", alias="extractionVersion")

    @model_validator(mode="after")
    def normalize_line_endings(self) -> "ExtractionRequest":
        self.raw_text = self.raw_text.replace("\r\n", "\n").replace("\r", "\n")
        return self


class NoteResponse(BaseModel):
    """Opaque source Note identity returned after a committed capture."""

    id: str
    recorded_at: datetime = Field(alias="recordedAt")


class CandidateResponse(BaseModel):
    """Project-scoped candidate handle and its source item."""

    handle: str = Field(pattern=r"^candidate-h-[0-9a-f]{24}$")
    id: str
    source_item_id: str = Field(alias="sourceItemId")
    status: Literal["extracted", "validated", "pending-review", "confirmed", "rejected", "asserted"]


class CaptureResponse(BaseModel):
    """Public result of an atomic capture."""

    request_id: str = Field(alias="requestId")
    note: NoteResponse
    candidates: list[CandidateResponse]
    replayed: bool = Field(default=False, exclude=True)


class RequirementAssertion(BaseModel):
    """The only assertion shape enabled by the M2 confirmation operation."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["Requirement"]
    label: str = Field(min_length=1, max_length=4096)
    valid_from: date = Field(alias="validFrom")


class ConfirmationRequest(BaseModel):
    """Released Requirement-only assertion payload."""

    model_config = ConfigDict(extra="forbid")
    assertion: RequirementAssertion
    correction_revision: int = Field(default=0, ge=0, alias="correctionRevision")


class RejectionRequest(BaseModel):
    """Human rejection reason."""

    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=4096)
