"""SourceVersion/source-receipt custody tests for the extraction boundary."""

from __future__ import annotations

import hashlib
import json
from typing import cast

import pytest
from pydantic import ValidationError

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.service import ExtractionOrchestrator, ExtractionPersistence
from projecta_api.extraction.source_version import (
    CANONICALIZATION_VERSION,
    COORDINATE_SYSTEM_VERSION,
    RetentionMetadata,
    SourceReceipt,
    SourceVersionVerificationError,
    create_source_version,
    serialize_source_receipt,
    verify_source_receipt,
)


def test_source_version_canonicalizes_newlines_without_changing_original_digest() -> None:
    original = b"first\r\nsecond\rthird\n"
    source = create_source_version(
        project_id="project-alpha",
        source_artifact_id="note-1",
        content=original,
    )

    assert source.original_content_digest == (
        "sha256:" + hashlib.sha256(original).hexdigest()
    )
    assert source.canonical_content_digest == (
        "sha256:" + hashlib.sha256(b"first\nsecond\nthird\n").hexdigest()
    )
    assert source.canonicalization_version == CANONICALIZATION_VERSION
    assert source.coordinate_system_version == COORDINATE_SYSTEM_VERSION


def test_source_version_preserves_combining_marks_and_emoji() -> None:
    text = "Cafe\u0301 🚀 — e\u0301"
    source = create_source_version(
        project_id="project-alpha",
        source_artifact_id="unicode-note",
        content=text,
    )

    expected = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert source.original_content_digest == expected
    assert source.canonical_content_digest == expected
    assert "Cafe\u0301" not in serialize_source_receipt(source.receipt())


def test_source_receipt_is_deterministic_and_contains_no_raw_content_or_ids() -> None:
    first = create_source_version(
        project_id="sensitive-project-name",
        source_artifact_id="sensitive-note-id",
        content="same\r\ntext",
    )
    second = create_source_version(
        project_id="sensitive-project-name",
        source_artifact_id="sensitive-note-id",
        content="same\r\ntext",
    )
    first_serialized = serialize_source_receipt(first.receipt())

    assert first.safe_dict() == second.safe_dict()
    assert first_serialized == serialize_source_receipt(second.receipt())
    assert "sensitive-project-name" not in first_serialized
    assert "sensitive-note-id" not in first_serialized
    assert "same" not in first_serialized
    assert list(json.loads(first_serialized)) == sorted(json.loads(first_serialized))


def test_source_receipt_verification_replays_exactly_and_rejects_tampering() -> None:
    source = create_source_version(
        project_id="project-alpha",
        source_artifact_id="note-1",
        content="stable text",
    )
    receipt = source.receipt()

    verify_source_receipt(
        receipt,
        project_id="project-alpha",
        source_artifact_id="note-1",
        content="stable text",
    )
    with pytest.raises(SourceVersionVerificationError, match="mismatch|fork"):
        verify_source_receipt(
            receipt,
            project_id="project-alpha",
            source_artifact_id="note-1",
            content="tampered text",
        )
    tampered = receipt.model_copy(
        update={"receipt_digest": "sha256:" + ("0" * 64)}
    )
    with pytest.raises(SourceVersionVerificationError, match="tampering|mismatch"):
        verify_source_receipt(
            tampered,
            project_id="project-alpha",
            source_artifact_id="note-1",
            content="stable text",
        )


def test_source_receipt_rejects_project_mismatch_and_parent_fork() -> None:
    parent = create_source_version(
        project_id="project-alpha",
        source_artifact_id="note-1",
        content="parent",
    )
    child = create_source_version(
        project_id="project-alpha",
        source_artifact_id="note-1",
        content="child",
        parent_source_version_id=parent.source_version_id,
        parent_canonical_content_digest=parent.canonical_content_digest,
    )

    with pytest.raises(SourceVersionVerificationError, match="project scope"):
        verify_source_receipt(
            child.receipt(),
            project_id="project-beta",
            source_artifact_id="note-1",
            content="child",
            parent_source_version_id=parent.source_version_id,
            parent_canonical_content_digest=parent.canonical_content_digest,
        )
    with pytest.raises(SourceVersionVerificationError, match="fork|mismatch"):
        verify_source_receipt(
            child.receipt(),
            project_id="project-alpha",
            source_artifact_id="note-1",
            content="child",
            parent_source_version_id=None,
            parent_canonical_content_digest=None,
        )
    with pytest.raises(ValueError, match="paired"):
        create_source_version(
            project_id="project-alpha",
            source_artifact_id="note-1",
            content="child",
            parent_source_version_id=parent.source_version_id,
        )


def test_source_receipt_fails_closed_for_encoding_digest_and_version_errors() -> None:
    with pytest.raises(SourceVersionVerificationError, match="UTF-8"):
        create_source_version(
            project_id="project-alpha",
            source_artifact_id="note-1",
            content=b"\xff\xfe",
        )
    source = create_source_version(
        project_id="project-alpha",
        source_artifact_id="note-1",
        content="valid",
    )
    with pytest.raises(ValidationError):
        SourceReceipt.model_validate(
            source.receipt().model_dump(by_alias=True)
            | {"canonicalizationVersion": "unknown.v9"}
        )
    with pytest.raises(ValidationError):
        SourceReceipt.model_validate(
            source.receipt().model_dump(by_alias=True)
            | {"canonicalContentDigest": "sha256:not-a-digest"}
        )


def test_orchestrator_exposes_source_version_as_explicit_opt_in() -> None:
    orchestrator = ExtractionOrchestrator(None, cast(ExtractionPersistence, object()), None)
    source = orchestrator.create_source_version(
        TrustedRequestContext("project-alpha", "actor", "request"),
        "note-1",
        "one\r\ntwo",
        retention=RetentionMetadata(policy="owner-gated"),
    )

    assert source.project_scope_id.startswith("project_")
    assert source.retention.policy == "owner-gated"
    assert source.canonical_content_digest != source.original_content_digest
