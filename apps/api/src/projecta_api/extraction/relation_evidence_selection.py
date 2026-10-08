"""Source-bound deterministic relation evidence selection (RM-59)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.extraction.confirmed_entity_gate import RelationAuthorization
from projecta_api.extraction.source_version import (
    SourceVersion,
    SourceVersionVerificationError,
    create_source_version,
    strict_utf8,
)
from projecta_api.extraction.text_anchor import (
    TextAnchor,
    TextAnchorVerificationError,
    verify_text_anchor,
)

RELATION_EVIDENCE_CONTRACT_VERSION: Final = "relation-evidence.v1"
SOURCE_BLOCK_CONTRACT_VERSION: Final = "source-block.v1"

EvidenceOutcome = Literal["selected", "review-required", "abstained", "quarantined"]
EvidenceReason = Literal[
    "SELECTED",
    "SOURCE_MISSING",
    "PROJECT_MISMATCH",
    "SOURCE_VERSION_MISMATCH",
    "SOURCE_STALE",
    "SOURCE_TAMPERED",
    "ENDPOINT_MISSING",
    "TRIGGER_MISSING",
    "ANCHOR_INVALID",
    "ANCHOR_OUT_OF_BLOCK",
    "NO_COMMON_BOUNDARY",
    "TIED_BOUNDARIES",
    "UNSUPPORTED_PREDICATE",
    "MALFORMED_REQUEST",
    "UNSUPPORTED_BLOCK_VERSION",
]
BlockKind = Literal["sentence", "clause"]

_PREDICATES: frozenset[str] = frozenset(
    {"implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy"}
)
_SENTENCE_TERMINATORS: frozenset[str] = frozenset(".!?。！？\n")
_CLAUSE_SEPARATORS: frozenset[str] = frozenset(",;:，；：")


class RelationEvidenceSelectionError(ValueError):
    """Raised only for malformed selector inputs; normal misses are outcomes."""

    def __init__(self, reason: EvidenceReason) -> None:
        self.reason = reason
        super().__init__(reason)


class SourceBlock(BaseModel):
    """Safe source block metadata; source text is deliberately not retained."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["source-block.v1"] = Field(
        default=SOURCE_BLOCK_CONTRACT_VERSION, alias="contractVersion"
    )
    block_id: str = Field(alias="blockId", pattern=r"^block_[0-9a-f]{64}$")
    source_version_id: str = Field(alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$")
    kind: BlockKind
    start_offset: int = Field(ge=0, alias="startOffset")
    end_offset: int = Field(gt=0, alias="endOffset")
    content_digest: str = Field(alias="contentDigest", pattern=r"^sha256:[0-9a-f]{64}$")

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


class RelationEvidenceSelection(BaseModel):
    """Safe selection outcome bound to relation endpoints and source version."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["relation-evidence.v1"] = Field(
        default=RELATION_EVIDENCE_CONTRACT_VERSION, alias="contractVersion"
    )
    outcome: EvidenceOutcome
    reason: EvidenceReason
    materializable: bool
    relation_id: str = Field(alias="relationId", pattern=r"^rel_[0-9a-f]{64}$")
    source_version_id: str = Field(alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$")
    source_handle: str = Field(alias="sourceHandle", pattern=r"^eh1_[0-9a-f]{64}$")
    target_handle: str = Field(alias="targetHandle", pattern=r"^eh1_[0-9a-f]{64}$")
    predicate: str
    block: SourceBlock | None = None
    source_anchor_digest: str | None = Field(default=None, alias="sourceAnchorDigest")
    target_anchor_digest: str | None = Field(default=None, alias="targetAnchorDigest")
    trigger_anchor_digest: str | None = Field(default=None, alias="triggerAnchorDigest")

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


def build_source_blocks(source: SourceVersion | None, content: bytes | str | None) -> list[SourceBlock]:
    """Build deterministic canonical sentence/clause block metadata."""

    canonical = _verified_canonical(source, content)
    if source is None:
        raise RelationEvidenceSelectionError("SOURCE_MISSING")
    ranges: list[tuple[BlockKind, int, int]] = []
    for sentence_start, sentence_end in _ranges(canonical, _SENTENCE_TERMINATORS):
        trimmed_sentence = _trim(canonical, sentence_start, sentence_end)
        if trimmed_sentence[0] < trimmed_sentence[1]:
            ranges.append(("sentence", trimmed_sentence[0], trimmed_sentence[1]))
        for clause_start, clause_end in _clause_ranges(canonical, sentence_start, sentence_end):
            trimmed_clause = _trim(canonical, clause_start, clause_end)
            if trimmed_clause[0] < trimmed_clause[1]:
                ranges.append(("clause", trimmed_clause[0], trimmed_clause[1]))
    blocks: list[SourceBlock] = []
    for kind, start, end in sorted(ranges, key=lambda item: (item[1], item[2], item[0])):
        block_text = canonical[start:end]
        digest = _sha256_digest(block_text.encode("utf-8", "strict"))
        blocks.append(
            SourceBlock(
                blockId=_block_id(source.source_version_id, kind, start, end, digest),
                sourceVersionId=source.source_version_id,
                kind=kind,
                startOffset=start,
                endOffset=end,
                contentDigest=digest,
            )
        )
    return blocks


def select_relation_evidence(
    project_id: str,
    source: SourceVersion | None,
    content: bytes | str | None,
    authorization: RelationAuthorization | None,
    source_anchor: TextAnchor | None,
    target_anchor: TextAnchor | None,
    *,
    trigger_anchor: TextAnchor | None = None,
    trigger_required: bool = False,
    server_blocks: Sequence[SourceBlock] | None = None,
) -> RelationEvidenceSelection:
    """Select the smallest valid server-owned boundary without textual fallback."""

    if source is None or content is None:
        return _outcome(authorization, "abstained", "SOURCE_MISSING")
    if source.project_id != project_id:
        return _outcome(authorization, "quarantined", "PROJECT_MISMATCH")
    if authorization is None:
        return _outcome(None, "quarantined", "MALFORMED_REQUEST")
    if authorization.source_version_id != source.source_version_id:
        return _outcome(authorization, "abstained", "SOURCE_VERSION_MISMATCH")
    if authorization.predicate not in _PREDICATES:
        return _outcome(authorization, "quarantined", "UNSUPPORTED_PREDICATE")
    if source_anchor is None or target_anchor is None:
        return _outcome(authorization, "abstained", "ENDPOINT_MISSING")
    if trigger_required and trigger_anchor is None:
        return _outcome(authorization, "abstained", "TRIGGER_MISSING")
    canonical: str
    try:
        canonical = _verified_canonical(source, content)
    except RelationEvidenceSelectionError as error:
        outcome: EvidenceOutcome = "abstained" if error.reason == "SOURCE_STALE" else "quarantined"
        return _outcome(authorization, outcome, cast(EvidenceReason, error.reason))
    for anchor in (source_anchor, target_anchor, trigger_anchor):
        if anchor is None:
            continue
        try:
            verify_text_anchor(anchor, source, content)
        except TextAnchorVerificationError as error:
            reason = _anchor_reason(error.reason)
            outcome = "abstained" if reason in {"SOURCE_STALE", "SOURCE_VERSION_MISMATCH"} else "quarantined"
            return _outcome(authorization, outcome, reason)
        except (TypeError, ValueError):
            return _outcome(authorization, "quarantined", "ANCHOR_INVALID")
    try:
        blocks = list(server_blocks) if server_blocks is not None else build_source_blocks(source, content)
        for block in blocks:
            _verify_block(block, source, canonical)
    except RelationEvidenceSelectionError as error:
        return _outcome(authorization, "quarantined", cast(EvidenceReason, error.reason))
    required_anchors = [source_anchor, target_anchor]
    if trigger_anchor is not None:
        required_anchors.append(trigger_anchor)
    candidates = [
        block
        for block in blocks
        if all(_contains(block, anchor) for anchor in required_anchors)
    ]
    if not candidates:
        return _outcome(authorization, "abstained", "NO_COMMON_BOUNDARY")
    candidates.sort(key=lambda block: (block.end_offset - block.start_offset, block.start_offset, block.end_offset))
    best_size = candidates[0].end_offset - candidates[0].start_offset
    best = [block for block in candidates if block.end_offset - block.start_offset == best_size]
    if len(best) != 1:
        return _outcome(
            authorization,
            "review-required",
            "TIED_BOUNDARIES",
            source_anchor=source_anchor,
            target_anchor=target_anchor,
            trigger_anchor=trigger_anchor,
        )
    selected = best[0]
    # Recompute the digest from verified canonical content to detect any block metadata drift.
    if _sha256_digest(canonical[selected.start_offset : selected.end_offset].encode("utf-8")) != selected.content_digest:
        return _outcome(authorization, "quarantined", "SOURCE_TAMPERED")
    return _outcome(
        authorization,
        "selected",
        "SELECTED",
        materializable=True,
        block=selected,
        source_anchor=source_anchor,
        target_anchor=target_anchor,
        trigger_anchor=trigger_anchor,
    )


def serialize_relation_evidence(selection: RelationEvidenceSelection) -> str:
    return json.dumps(selection.safe_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _outcome(
    authorization: RelationAuthorization | None,
    outcome: EvidenceOutcome,
    reason: EvidenceReason,
    *,
    materializable: bool = False,
    block: SourceBlock | None = None,
    source_anchor: TextAnchor | None = None,
    target_anchor: TextAnchor | None = None,
    trigger_anchor: TextAnchor | None = None,
) -> RelationEvidenceSelection:
    if authorization is None:
        # This is only reached for malformed calls; safe placeholder IDs preserve schema strictness.
        relation_id = "rel_" + ("0" * 64)
        source_version_id = "sv_" + ("0" * 64)
        source_handle = "eh1_" + ("0" * 64)
        target_handle = "eh1_" + ("1" * 64)
        predicate = "supports"
    else:
        relation_id = authorization.relation_id
        source_version_id = authorization.source_version_id
        source_handle = authorization.source_handle
        target_handle = authorization.target_handle
        predicate = authorization.predicate
    return RelationEvidenceSelection(
        outcome=outcome,
        reason=reason,
        materializable=materializable and outcome == "selected" and reason == "SELECTED",
        relationId=relation_id,
        sourceVersionId=source_version_id,
        sourceHandle=source_handle,
        targetHandle=target_handle,
        predicate=predicate,
        block=block,
        sourceAnchorDigest=_anchor_digest(source_anchor),
        targetAnchorDigest=_anchor_digest(target_anchor),
        triggerAnchorDigest=_anchor_digest(trigger_anchor),
    )


def _verified_canonical(source: SourceVersion | None, content: bytes | str | None) -> str:
    if source is None or content is None:
        raise RelationEvidenceSelectionError("SOURCE_MISSING")
    try:
        original_bytes, decoded = strict_utf8(content)
        canonical = decoded.replace("\r\n", "\n").replace("\r", "\n")
        rebuilt = create_source_version(
            project_id=source.project_id,
            source_artifact_id=source.source_artifact_id,
            content=content,
            parent_source_version_id=source.parent_source_version_id,
            parent_canonical_content_digest=source.parent_canonical_content_digest,
            retention=source.retention,
        )
    except (TypeError, UnicodeError, SourceVersionVerificationError, ValueError) as error:
        raise RelationEvidenceSelectionError("SOURCE_TAMPERED") from error
    if rebuilt.canonical_content_digest != source.canonical_content_digest:
        raise RelationEvidenceSelectionError("SOURCE_STALE")
    if rebuilt.source_version_id != source.source_version_id or rebuilt.original_content_digest != source.original_content_digest:
        raise RelationEvidenceSelectionError("SOURCE_TAMPERED")
    if len(original_bytes) != len(decoded.encode("utf-8", "strict")):
        raise RelationEvidenceSelectionError("SOURCE_TAMPERED")
    return canonical


def _ranges(text: str, terminators: frozenset[str]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start = 0
    for index, character in enumerate(text):
        if character in terminators:
            result.append((start, index + 1))
            start = index + 1
    if start < len(text):
        result.append((start, len(text)))
    return result


def _clause_ranges(text: str, start: int, end: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    clause_start = start
    for index in range(start, end):
        if text[index] in _CLAUSE_SEPARATORS:
            if clause_start < index:
                ranges.append((clause_start, index))
            clause_start = index + 1
    if clause_start < end:
        ranges.append((clause_start, end))
    return ranges if len(ranges) > 1 else []


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _contains(block: SourceBlock, anchor: TextAnchor) -> bool:
    return block.start_offset <= anchor.start_offset and anchor.end_offset <= block.end_offset


def _verify_block(block: SourceBlock, source: SourceVersion, canonical: str) -> None:
    if block.source_version_id != source.source_version_id:
        raise RelationEvidenceSelectionError("SOURCE_VERSION_MISMATCH")
    if block.end_offset > len(canonical) or block.start_offset >= block.end_offset:
        raise RelationEvidenceSelectionError("SOURCE_TAMPERED")
    digest = _sha256_digest(canonical[block.start_offset : block.end_offset].encode("utf-8", "strict"))
    if digest != block.content_digest:
        raise RelationEvidenceSelectionError("SOURCE_TAMPERED")
    if block.block_id != _block_id(
        source.source_version_id,
        block.kind,
        block.start_offset,
        block.end_offset,
        block.content_digest,
    ):
        raise RelationEvidenceSelectionError("SOURCE_TAMPERED")


def _block_id(source_version_id: str, kind: str, start: int, end: int, digest: str) -> str:
    return "block_" + hashlib.sha256(
        _stable_json({"sourceVersionId": source_version_id, "kind": kind, "start": start, "end": end, "digest": digest})
    ).hexdigest()


def _anchor_digest(anchor: TextAnchor | None) -> str | None:
    if anchor is None:
        return None
    return _sha256_digest(_stable_json(anchor.safe_dict()))


def _anchor_reason(reason: str) -> EvidenceReason:
    if reason in {"SOURCE_MISSING", "SOURCE_VERSION_MISMATCH", "SOURCE_STALE", "SOURCE_TAMPERED"}:
        return cast(EvidenceReason, reason)
    return "ANCHOR_INVALID"


def _sha256_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _stable_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8", "strict")
