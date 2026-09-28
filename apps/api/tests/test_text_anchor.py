"""Source-bound TextAnchor coordinate and fail-closed verification tests."""

from __future__ import annotations

import json
from typing import cast

import pytest
from pydantic import ValidationError

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.service import ExtractionOrchestrator, ExtractionPersistence
from projecta_api.extraction.source_version import create_source_version
from projecta_api.extraction.text_anchor import (
    TextAnchorVerificationError,
    resolve_text_anchor,
    serialize_text_anchor,
    verify_text_anchor,
)


def _source(content: str):
    return create_source_version(
        project_id="project-alpha", source_artifact_id="note-1", content=content
    )


def test_ascii_anchor_uses_zero_based_half_open_codepoint_and_utf16_offsets() -> None:
    source = _source("alpha beta")

    anchor = resolve_text_anchor(source, "alpha beta", "beta")

    assert (anchor.start_offset, anchor.end_offset) == (6, 10)
    assert (anchor.original_start_offset, anchor.original_end_offset) == (6, 10)
    assert (anchor.original_start_byte, anchor.original_end_byte) == (6, 10)
    assert (anchor.utf16_start_offset, anchor.utf16_end_offset) == (6, 10)


@pytest.mark.parametrize("content", ["a\r\nb", "a\rb", "a\nb"])
def test_newline_variants_map_canonical_newline_to_original_bytes(content: str) -> None:
    source = _source(content)

    anchor = resolve_text_anchor(source, content, "b")

    assert (anchor.start_offset, anchor.end_offset) == (2, 3)
    assert anchor.original_start_offset == len(content) - 1
    assert anchor.original_end_offset == len(content)
    assert anchor.original_start_byte == len(content.encode("utf-8")) - 1


def test_unicode_anchor_counts_emoji_as_two_utf16_units_but_one_codepoint() -> None:
    content = "A🚀e\u0301漢字"
    source = _source(content)

    anchor = resolve_text_anchor(source, content, "🚀e\u0301漢")

    assert (anchor.start_offset, anchor.end_offset) == (1, 5)
    assert (anchor.utf16_start_offset, anchor.utf16_end_offset) == (1, 6)
    assert (anchor.original_start_byte, anchor.original_end_byte) == (1, 1 + len("🚀e\u0301漢".encode()))


def test_repeated_and_nested_mentions_require_explicit_occurrence() -> None:
    content = "alpha alpha"
    source = _source(content)

    with pytest.raises(TextAnchorVerificationError) as ambiguous:
        resolve_text_anchor(source, content, "alpha")
    assert ambiguous.value.reason == "AMBIGUOUS_REPEATED_QUOTE"

    second = resolve_text_anchor(source, content, "alpha", occurrence=2)
    assert (second.start_offset, second.end_offset) == (6, 11)
    nested = resolve_text_anchor(source, content, "lph", occurrence=2)
    assert (nested.start_offset, nested.end_offset) == (7, 10)


def test_verification_rejects_source_stale_and_metadata_tampering() -> None:
    source = _source("stable text")
    anchor = resolve_text_anchor(source, "stable text", "stable")

    with pytest.raises(TextAnchorVerificationError) as stale:
        verify_text_anchor(anchor, source, "changed text")
    assert stale.value.reason == "SOURCE_STALE"

    tampered = anchor.model_copy(update={"original_start_byte": anchor.original_start_byte + 1})
    with pytest.raises(TextAnchorVerificationError) as mismatch:
        verify_text_anchor(tampered, source, "stable text")
    assert mismatch.value.reason == "MAPPING_MISMATCH"

    other_source = create_source_version(
        project_id="project-alpha", source_artifact_id="note-2", content="stable text"
    )
    other_anchor = resolve_text_anchor(other_source, "stable text", "stable")
    with pytest.raises(TextAnchorVerificationError) as source_mismatch:
        verify_text_anchor(other_anchor, source, "stable text")
    assert source_mismatch.value.reason == "SOURCE_VERSION_MISMATCH"


@pytest.mark.parametrize(
    ("update", "reason"),
    [
        ({"start_offset": -1}, "NEGATIVE_OFFSET"),
        ({"start_offset": 4, "end_offset": 3}, "REVERSED_RANGE"),
        ({"start_offset": 0, "end_offset": 0}, "EMPTY_RANGE"),
        ({"start_offset": 0, "end_offset": 99}, "OUT_OF_RANGE"),
        ({"exact_quote": "wrong"}, "EXACT_QUOTE_MISMATCH"),
        ({"quote_digest": "sha256:" + "0" * 64}, "QUOTE_DIGEST_MISMATCH"),
        ({"coordinate_system_version": "unknown.v9"}, "UNSUPPORTED_COORDINATE_VERSION"),
    ],
)
def test_verification_has_finite_fail_closed_reasons(update: dict[str, object], reason: str) -> None:
    source = _source("alpha beta")
    anchor = resolve_text_anchor(source, "alpha beta", "beta")
    tampered = anchor.model_copy(update=update)

    with pytest.raises(TextAnchorVerificationError) as failure:
        verify_text_anchor(tampered, source, "alpha beta")
    assert failure.value.reason == reason


def test_resolution_rejects_invalid_unicode_and_missing_or_bad_occurrence() -> None:
    source = _source("valid")
    with pytest.raises(TextAnchorVerificationError, match="INVALID_UNICODE"):
        resolve_text_anchor(source, "valid\ud800", "valid")
    with pytest.raises(TextAnchorVerificationError, match="SOURCE_MISSING"):
        resolve_text_anchor(None, None, "valid")
    with pytest.raises(TextAnchorVerificationError, match="OCCURRENCE_OUT_OF_RANGE"):
        resolve_text_anchor(source, "valid", "valid", occurrence=2)
    with pytest.raises(TextAnchorVerificationError, match="MISSING_QUOTE"):
        resolve_text_anchor(source, "valid", "absent")


def test_project_mismatch_is_rejected_at_explicit_orchestrator_opt_in() -> None:
    orchestrator = ExtractionOrchestrator(None, cast(ExtractionPersistence, object()), None)
    source = orchestrator.create_source_version(
        TrustedRequestContext("project-alpha", "actor", "request"), "note-1", "alpha"
    )

    with pytest.raises(TextAnchorVerificationError, match="SOURCE_VERSION_MISMATCH"):
        orchestrator.resolve_text_anchor(
            TrustedRequestContext("project-beta", "actor", "request-2"),
            source,
            "alpha",
            "alpha",
        )


def test_anchor_serialization_is_deterministic_and_excludes_raw_quote() -> None:
    source = _source("private alpha")
    anchor = resolve_text_anchor(source, "private alpha", "private")

    first = serialize_text_anchor(anchor)
    second = serialize_text_anchor(anchor)

    assert first == second
    assert "private" not in first
    assert "exactQuote" not in first
    assert list(json.loads(first)) == sorted(json.loads(first))


def test_anchor_model_rejects_invalid_digest_and_empty_ranges() -> None:
    source = _source("alpha")
    anchor = resolve_text_anchor(source, "alpha", "alpha")
    with pytest.raises(ValidationError):
        type(anchor).model_validate(
            anchor.model_dump(by_alias=True) | {"quoteDigest": "not-a-digest"}
        )
    with pytest.raises(ValidationError):
        type(anchor).model_validate(
            anchor.model_dump(by_alias=True)
            | {"startOffset": 0, "endOffset": 0}
        )
