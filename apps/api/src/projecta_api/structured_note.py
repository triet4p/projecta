"""Strict application contract for a structured Note draft.

The draft is intentionally an application boundary. Its workflow fields are
not ontology assertions; the semantic write boundary remains governed by the
released Note/NoteItem vocabulary and the S8-53 review gate.
"""

from datetime import date as Date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

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
NoteDraftStatus = Literal["draft", "ready", "committed", "abstained"]
NoteSourceKind = Literal["manual", "text-import", "connector"]
CandidateEditType = Literal[
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
CandidateRelation = Literal[
    "implements",
    "blocks",
    "dependsOn",
    "supports",
    "answers",
    "resolves",
    "constrainedBy",
]
OpaqueReference = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]


def _normalize_line_endings(value: str) -> str:
    """Use one deterministic line separator for all canonical text."""
    return value.replace("\r\n", "\n").replace("\r", "\n")


class NoteSourceMetadata(BaseModel):
    """Optional non-semantic origin metadata for the draft workflow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    kind: NoteSourceKind
    label: str | None = Field(default=None, max_length=256)
    reference: str | None = Field(default=None, max_length=512)


class StructuredNoteItemDraft(BaseModel):
    """One ordered, typed source item supplied by a composer or importer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    item_type: NoteItemType = Field(alias="itemType")
    content: str = Field(min_length=1, max_length=16_384)

    @model_validator(mode="after")
    def normalize_content(self) -> "StructuredNoteItemDraft":
        self.content = _normalize_line_endings(self.content)
        return self


class StructuredNoteDraft(BaseModel):
    """Editable structured Note input with server-owned text derivation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    title: str = Field(min_length=1, max_length=512)
    items: list[StructuredNoteItemDraft] = Field(default_factory=lambda: [], max_length=256)
    draft_status: NoteDraftStatus = Field(default="draft", alias="draftStatus")
    source_metadata: NoteSourceMetadata | None = Field(default=None, alias="sourceMetadata")

    @model_validator(mode="after")
    def normalize_title(self) -> "StructuredNoteDraft":
        self.title = _normalize_line_endings(self.title)
        return self


class StructuredNoteItemProjection(BaseModel):
    """Server-derived item representation with exact evidence offsets."""

    model_config = ConfigDict(populate_by_name=True)

    item_type: NoteItemType = Field(alias="itemType")
    content: str
    start_offset: int = Field(ge=0, alias="startOffset")
    end_offset: int = Field(gt=0, alias="endOffset")


class StructuredNoteCanonical(BaseModel):
    """Canonical draft payload passed to later semantic/API boundaries."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    items: list[StructuredNoteItemProjection]
    raw_text: str = Field(alias="rawText")
    draft_status: NoteDraftStatus = Field(alias="draftStatus")
    source_metadata: NoteSourceMetadata | None = Field(default=None, alias="sourceMetadata")


class StructuredNoteDraftResponse(StructuredNoteCanonical):
    """Public draft representation with an opaque application handle."""

    request_id: str = Field(alias="requestId")
    draft_handle: str = Field(alias="draftHandle")
    revision: int = Field(ge=1)
    committed_note_handle: str | None = Field(default=None, alias="committedNoteHandle")
    replayed: bool = Field(default=False, exclude=True)


class StructuredNoteListItem(BaseModel):
    """Bounded human-readable Note list projection."""

    model_config = ConfigDict(populate_by_name=True)

    handle: str
    title: str
    author: str
    recorded_at: str = Field(alias="recordedAt")
    item_type_summary: list[NoteItemType] = Field(alias="itemTypeSummary")
    candidate_state: str = Field(alias="candidateState")
    evidence_coverage: float = Field(ge=0, le=1, alias="evidenceCoverage")


class StructuredNoteListResponse(BaseModel):
    """Finite Note list response."""

    request_id: str = Field(alias="requestId")
    drafts: list[StructuredNoteDraftResponse]
    committed: list[StructuredNoteListItem]


class StructuredNoteDetailResponse(BaseModel):
    """Exact source detail projection; raw text is never redacted or rewritten."""

    request_id: str = Field(alias="requestId")
    note_handle: str = Field(alias="noteHandle")
    title: str
    raw_text: str = Field(alias="rawText")
    author: str
    recorded_at: str = Field(alias="recordedAt")
    items: list[StructuredNoteItemProjection]
    evidence_coverage: float = Field(ge=0, le=1, alias="evidenceCoverage")
    candidate_state: str = Field(alias="candidateState")


class StructuredNoteImportRequest(BaseModel):
    """Pasted text submitted for assisted, non-persisting import."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    title: str | None = Field(default=None, max_length=512)
    raw_text: str = Field(min_length=1, max_length=100_000, alias="rawText")

    @model_validator(mode="after")
    def normalize_text(self) -> "StructuredNoteImportRequest":
        self.raw_text = _normalize_line_endings(self.raw_text)
        if self.title is not None:
            self.title = _normalize_line_endings(self.title)
        return self


class StructuredNoteRelationProposal(BaseModel):
    """Optional relation proposal kept separate from source Note semantics."""

    relation: CandidateRelation
    source_index: int = Field(ge=0, alias="sourceIndex")
    target_index: int = Field(ge=0, alias="targetIndex")


class StructuredNoteImportResponse(BaseModel):
    """Every proposed item or an explicit abstention; never an auto-save."""

    request_id: str = Field(alias="requestId")
    status: Literal["proposed", "abstained"]
    title: str | None = None
    proposals: list[StructuredNoteItemDraft]
    relations: list[StructuredNoteRelationProposal] = Field(default_factory=lambda: [])
    abstention_reason: str | None = Field(default=None, alias="abstentionReason")


class StructuredCandidateEditRequest(BaseModel):
    """Finite pre-confirmation candidate correction payload."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    entity_type: CandidateEditType | None = Field(default=None, alias="entityType")
    label: str | None = Field(default=None, min_length=1, max_length=4096)
    relation: CandidateRelation | None = None
    entity_link: OpaqueReference | None = Field(default=None, alias="entityLink")
    date: Date | None = None
    assignment: OpaqueReference | None = None
    expected_revision: int = Field(default=1, ge=1, alias="expectedRevision")

    @model_validator(mode="after")
    def require_one_edit(self) -> "StructuredCandidateEditRequest":
        if all(
            value is None
            for value in (
                self.entity_type,
                self.label,
                self.relation,
                self.entity_link,
                self.date,
                self.assignment,
            )
        ):
            raise ValueError("at least one candidate correction is required")
        return self


class CandidateEditOption(BaseModel):
    """One server-owned labeled correction target; the handle is never user-entered."""

    handle: OpaqueReference
    label: str = Field(min_length=1, max_length=500)
    type: str = Field(min_length=1, max_length=128)


class CandidateEditOptionsResponse(BaseModel):
    """Finite project-scoped options for candidate relationship corrections."""

    request_id: str = Field(alias="requestId")
    entity_links: list[CandidateEditOption] = Field(alias="entityLinks")
    assignments: list[CandidateEditOption]


def canonicalize_structured_note(draft: StructuredNoteDraft) -> StructuredNoteCanonical:
    """Derive raw text and non-overlapping code-point offsets deterministically.

    Raw text is the normalized item content joined by one LF. The title is
    Note metadata and is therefore not included in the evidence body. Empty
    drafts are valid while editing; commit-time validation belongs to S8-54.
    """
    raw_text = "\n".join(item.content for item in draft.items)
    projected_items: list[StructuredNoteItemProjection] = []
    cursor = 0
    for index, item in enumerate(draft.items):
        start_offset = cursor
        end_offset = start_offset + len(item.content)
        projected_items.append(
            StructuredNoteItemProjection(
                itemType=item.item_type,
                content=item.content,
                startOffset=start_offset,
                endOffset=end_offset,
            )
        )
        cursor = end_offset + (1 if index < len(draft.items) - 1 else 0)

    return StructuredNoteCanonical(
        title=draft.title,
        items=projected_items,
        rawText=raw_text,
        draftStatus=draft.draft_status,
        sourceMetadata=draft.source_metadata,
    )
