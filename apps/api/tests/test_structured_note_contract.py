"""Contract tests for server-derived structured Note drafts."""

import pytest
from pydantic import ValidationError

from projecta_api.structured_note import (
    StructuredNoteDraft,
    canonicalize_structured_note,
)


def test_canonicalization_preserves_order_and_derives_offsets() -> None:
    draft = StructuredNoteDraft.model_validate(
        {
            "title": "Checkout plan",
            "items": [
                {"itemType": "requirement", "content": "Confirm address."},
                {"itemType": "task", "content": "Ask Le to verify."},
            ],
            "draftStatus": "ready",
        }
    )

    result = canonicalize_structured_note(draft)

    assert result.raw_text == "Confirm address.\nAsk Le to verify."
    assert [(item.start_offset, item.end_offset) for item in result.items] == [(0, 16), (17, 34)]
    assert [item.content for item in result.items] == ["Confirm address.", "Ask Le to verify."]
    assert result.draft_status == "ready"


def test_offsets_count_unicode_code_points_and_normalize_line_endings() -> None:
    draft = StructuredNoteDraft.model_validate(
        {
            "title": "Unicode",
            "items": [
                {"itemType": "question", "content": "Café 🚀\r\nNeed review"},
                {"itemType": "risk", "content": "Duplicate 🚀"},
            ],
        }
    )

    result = canonicalize_structured_note(draft)

    assert result.raw_text == "Café 🚀\nNeed review\nDuplicate 🚀"
    assert result.items[0].content == "Café 🚀\nNeed review"
    assert result.items[0].end_offset == len("Café 🚀\nNeed review")
    assert result.items[1].start_offset == result.items[0].end_offset + 1
    assert (
        result.raw_text[result.items[1].start_offset : result.items[1].end_offset] == "Duplicate 🚀"
    )


def test_empty_items_are_valid_for_an_editable_draft() -> None:
    result = canonicalize_structured_note(
        StructuredNoteDraft.model_validate({"title": "Untitled", "items": []})
    )

    assert result.raw_text == ""
    assert result.items == []
    assert result.draft_status == "draft"


def test_duplicate_item_content_remains_two_distinct_ordered_items() -> None:
    result = canonicalize_structured_note(
        StructuredNoteDraft.model_validate(
            {
                "title": "Repeated",
                "items": [
                    {"itemType": "task", "content": "Review it."},
                    {"itemType": "task", "content": "Review it."},
                ],
            }
        )
    )

    assert result.raw_text == "Review it.\nReview it."
    assert result.items[0].start_offset == 0
    assert result.items[1].start_offset == len("Review it.") + 1
    assert result.items[0].start_offset != result.items[1].start_offset


def test_invalid_item_type_and_extra_fields_fail_closed() -> None:
    with pytest.raises(ValidationError):
        StructuredNoteDraft.model_validate(
            {"title": "Bad", "items": [{"itemType": "todo", "content": "Do it."}]}
        )

    with pytest.raises(ValidationError):
        StructuredNoteDraft.model_validate(
            {
                "title": "Bad",
                "items": [{"itemType": "task", "content": "Do it.", "startOffset": 0}],
            }
        )


def test_source_metadata_is_optional_and_strict() -> None:
    draft = StructuredNoteDraft.model_validate(
        {
            "title": "Imported",
            "sourceMetadata": {
                "kind": "text-import",
                "label": "Meeting transcript",
                "reference": "import-2026-08-10-01",
            },
        }
    )

    result = canonicalize_structured_note(draft)

    assert result.source_metadata is not None
    assert result.source_metadata.kind == "text-import"
