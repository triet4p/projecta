"""Verified source-bound text anchors and server-owned coordinate mappings."""

from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from projecta_api.extraction.source_version import (
    COORDINATE_SYSTEM_VERSION,
    SourceVersion,
    SourceVersionVerificationError,
    create_source_version,
    strict_utf8,
)

TEXT_ANCHOR_CONTRACT_VERSION: Final = "text-anchor.v1"

TextAnchorFailureReason = Literal[
    "SOURCE_MISSING",
    "SOURCE_VERSION_MISMATCH",
    "SOURCE_TAMPERED",
    "SOURCE_STALE",
    "NEGATIVE_OFFSET",
    "REVERSED_RANGE",
    "EMPTY_RANGE",
    "OUT_OF_RANGE",
    "EXACT_QUOTE_MISMATCH",
    "QUOTE_DIGEST_MISMATCH",
    "MISSING_QUOTE",
    "AMBIGUOUS_REPEATED_QUOTE",
    "OCCURRENCE_OUT_OF_RANGE",
    "INVALID_UNICODE",
    "UNSUPPORTED_COORDINATE_VERSION",
    "MAPPING_MISMATCH",
]


class TextAnchorVerificationError(ValueError):
    """Raised when a text anchor cannot be verified without fallback."""

    def __init__(self, reason: TextAnchorFailureReason) -> None:
        self.reason = reason
        super().__init__(reason)


class TextAnchor(BaseModel):
    """A source-version-bound canonical span with server-derived mappings."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["text-anchor.v1"] = Field(
        default=TEXT_ANCHOR_CONTRACT_VERSION, alias="contractVersion"
    )
    source_version_id: str = Field(
        alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$"
    )
    canonical_content_digest: str = Field(
        alias="canonicalContentDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    start_offset: int = Field(ge=0, alias="startOffset")
    end_offset: int = Field(ge=0, alias="endOffset")
    exact_quote: str = Field(min_length=1, alias="exactQuote")
    quote_digest: str = Field(alias="quoteDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    block_id: str | None = Field(default=None, alias="blockId", min_length=1)
    occurrence: int | None = Field(default=None, ge=1)
    coordinate_system_version: Literal["unicode-codepoint.v1"] = Field(
        default=COORDINATE_SYSTEM_VERSION, alias="coordinateSystemVersion"
    )
    original_start_offset: int = Field(ge=0, alias="originalStartOffset")
    original_end_offset: int = Field(ge=0, alias="originalEndOffset")
    original_start_byte: int = Field(ge=0, alias="originalStartByte")
    original_end_byte: int = Field(ge=0, alias="originalEndByte")
    utf16_start_offset: int = Field(ge=0, alias="utf16StartOffset")
    utf16_end_offset: int = Field(ge=0, alias="utf16EndOffset")

    @model_validator(mode="after")
    def validate_ranges(self) -> TextAnchor:
        if self.start_offset >= self.end_offset:
            raise ValueError("text anchor must have a non-empty half-open range")
        if self.original_start_offset >= self.original_end_offset:
            raise ValueError("original mapping must have a non-empty range")
        if self.original_start_byte >= self.original_end_byte:
            raise ValueError("original byte mapping must have a non-empty range")
        if self.utf16_start_offset >= self.utf16_end_offset:
            raise ValueError("UTF-16 mapping must have a non-empty range")
        return self

    def safe_dict(self) -> dict[str, object]:
        """Serialize anchor metadata without the raw quote."""

        data = self.model_dump(mode="json", by_alias=True)
        data.pop("exactQuote", None)
        return cast(dict[str, object], data)


def resolve_text_anchor(
    source: SourceVersion | None,
    content: bytes | str | None,
    exact_quote: str,
    *,
    occurrence: int | None = None,
    block_id: str | None = None,
) -> TextAnchor:
    """Resolve one quote in verified canonical content, failing on ambiguity."""

    canonical, original_byte_boundaries, canonical_to_original = _verified_source_maps(
        source, content
    )
    if not exact_quote:
        raise TextAnchorVerificationError("EMPTY_RANGE")
    try:
        exact_quote.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise TextAnchorVerificationError("INVALID_UNICODE") from error
    matches = _all_occurrences(canonical, exact_quote)
    if not matches:
        raise TextAnchorVerificationError("MISSING_QUOTE")
    if occurrence is None:
        if len(matches) > 1:
            raise TextAnchorVerificationError("AMBIGUOUS_REPEATED_QUOTE")
        selected = matches[0]
        selected_occurrence: int | None = None
    else:
        if occurrence < 1 or occurrence > len(matches):
            raise TextAnchorVerificationError("OCCURRENCE_OUT_OF_RANGE")
        selected = matches[occurrence - 1]
        selected_occurrence = occurrence
    end = selected + len(exact_quote)
    mapping = _mapping_for_range(
        canonical,
        selected,
        end,
        canonical_to_original,
        original_byte_boundaries,
    )
    anchor = TextAnchor.model_validate(
        {
            "sourceVersionId": source.source_version_id if source else "",
            "canonicalContentDigest": source.canonical_content_digest if source else "",
            "startOffset": selected,
            "endOffset": end,
            "exactQuote": exact_quote,
            "quoteDigest": _digest(exact_quote.encode("utf-8")),
            "blockId": block_id,
            "occurrence": selected_occurrence,
            "coordinateSystemVersion": COORDINATE_SYSTEM_VERSION,
            **mapping,
        }
    )
    verify_text_anchor(anchor, source, content)
    return anchor


def verify_text_anchor(
    anchor: TextAnchor | None,
    source: SourceVersion | None,
    content: bytes | str | None,
) -> None:
    """Verify source identity, exact quote, range and every coordinate mapping."""

    if anchor is None or source is None or content is None:
        raise TextAnchorVerificationError("SOURCE_MISSING")
    if anchor.coordinate_system_version != COORDINATE_SYSTEM_VERSION:
        raise TextAnchorVerificationError("UNSUPPORTED_COORDINATE_VERSION")
    if source.coordinate_system_version != COORDINATE_SYSTEM_VERSION:
        raise TextAnchorVerificationError("UNSUPPORTED_COORDINATE_VERSION")
    if anchor.source_version_id != source.source_version_id:
        raise TextAnchorVerificationError("SOURCE_VERSION_MISMATCH")
    if anchor.canonical_content_digest != source.canonical_content_digest:
        raise TextAnchorVerificationError("SOURCE_VERSION_MISMATCH")
    canonical, original_byte_boundaries, canonical_to_original = _verified_source_maps(
        source, content
    )
    _validate_anchor_range(anchor, len(canonical))
    actual_quote = canonical[anchor.start_offset : anchor.end_offset]
    if actual_quote != anchor.exact_quote:
        raise TextAnchorVerificationError("EXACT_QUOTE_MISMATCH")
    if _digest(anchor.exact_quote.encode("utf-8")) != anchor.quote_digest:
        raise TextAnchorVerificationError("QUOTE_DIGEST_MISMATCH")
    expected_mapping = _mapping_for_range(
        canonical,
        anchor.start_offset,
        anchor.end_offset,
        canonical_to_original,
        original_byte_boundaries,
    )
    actual_mapping = {
        "originalStartOffset": anchor.original_start_offset,
        "originalEndOffset": anchor.original_end_offset,
        "originalStartByte": anchor.original_start_byte,
        "originalEndByte": anchor.original_end_byte,
        "utf16StartOffset": anchor.utf16_start_offset,
        "utf16EndOffset": anchor.utf16_end_offset,
    }
    if expected_mapping != actual_mapping:
        raise TextAnchorVerificationError("MAPPING_MISMATCH")


def serialize_text_anchor(anchor: TextAnchor) -> str:
    """Return deterministic telemetry-safe metadata without quote or content."""

    return json.dumps(
        anchor.safe_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _verified_source_maps(
    source: SourceVersion | None,
    content: bytes | str | None,
) -> tuple[str, list[int], list[int]]:
    if source is None or content is None:
        raise TextAnchorVerificationError("SOURCE_MISSING")
    try:
        original_bytes, original = strict_utf8(content)
    except (TypeError, SourceVersionVerificationError, UnicodeError) as error:
        raise TextAnchorVerificationError("INVALID_UNICODE") from error
    try:
        rebuilt = create_source_version(
            project_id=source.project_id,
            source_artifact_id=source.source_artifact_id,
            content=content,
            parent_source_version_id=source.parent_source_version_id,
            parent_canonical_content_digest=source.parent_canonical_content_digest,
            retention=source.retention,
        )
    except (TypeError, SourceVersionVerificationError, UnicodeError, ValueError) as error:
        raise TextAnchorVerificationError("SOURCE_TAMPERED") from error
    if (
        rebuilt.canonical_content_digest != source.canonical_content_digest
    ):
        raise TextAnchorVerificationError("SOURCE_STALE")
    if (
        rebuilt.source_version_id != source.source_version_id
        or rebuilt.original_content_digest != source.original_content_digest
        or rebuilt.canonicalization_version != source.canonicalization_version
    ):
        raise TextAnchorVerificationError("SOURCE_TAMPERED")
    canonical_chars: list[str] = []
    canonical_to_original = [0]
    original_index = 0
    while original_index < len(original):
        character = original[original_index]
        if character == "\r" and original_index + 1 < len(original) and original[original_index + 1] == "\n":
            canonical_chars.append("\n")
            original_index += 2
        elif character == "\r":
            canonical_chars.append("\n")
            original_index += 1
        else:
            canonical_chars.append(character)
            original_index += 1
        canonical_to_original.append(original_index)
    canonical = "".join(canonical_chars)
    original_byte_boundaries = [0]
    for character in original:
        original_byte_boundaries.append(
            original_byte_boundaries[-1] + len(character.encode("utf-8", "strict"))
        )
    if original_byte_boundaries[-1] != len(original_bytes):
        raise TextAnchorVerificationError("SOURCE_TAMPERED")
    return canonical, original_byte_boundaries, canonical_to_original


def _validate_anchor_range(anchor: TextAnchor, canonical_length: int) -> None:
    if anchor.start_offset < 0 or anchor.end_offset < 0:
        raise TextAnchorVerificationError("NEGATIVE_OFFSET")
    if anchor.start_offset > anchor.end_offset:
        raise TextAnchorVerificationError("REVERSED_RANGE")
    if anchor.start_offset == anchor.end_offset:
        raise TextAnchorVerificationError("EMPTY_RANGE")
    if anchor.end_offset > canonical_length:
        raise TextAnchorVerificationError("OUT_OF_RANGE")


def _mapping_for_range(
    canonical: str,
    start: int,
    end: int,
    canonical_to_original: list[int],
    original_byte_boundaries: list[int],
) -> dict[str, int]:
    original_start = canonical_to_original[start]
    original_end = canonical_to_original[end]
    utf16_boundaries = [0]
    for character in canonical:
        utf16_boundaries.append(utf16_boundaries[-1] + (2 if ord(character) > 0xFFFF else 1))
    return {
        "originalStartOffset": original_start,
        "originalEndOffset": original_end,
        "originalStartByte": original_byte_boundaries[original_start],
        "originalEndByte": original_byte_boundaries[original_end],
        "utf16StartOffset": utf16_boundaries[start],
        "utf16EndOffset": utf16_boundaries[end],
    }


def _all_occurrences(text: str, quote: str) -> list[int]:
    matches: list[int] = []
    cursor = 0
    while cursor <= len(text) - len(quote):
        index = text.find(quote, cursor)
        if index < 0:
            break
        matches.append(index)
        cursor = index + 1
    return matches


def _digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"
