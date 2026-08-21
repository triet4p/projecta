from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
DIAGNOSTIC = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm30-offline-diagnostic-report.v1.json"
SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-offline-diagnostic-report.schema.v1.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm30-offline-remediation.v1.json"

import sys

sys.path.insert(0, str(ROOT / "scripts"))

from s12_f12_rm30_diagnostic_remediation import (  # noqa: E402
    EVIDENCE_REASON_CODES,
    SCHEMA_REASON_CODES,
    build_from_historical_report,
    classify_schema_failure,
    diagnose_evidence_failure,
    historical_evidence_failure,
    normalize_evidence_failure,
)
from sprint12_f12_two_step_contracts_v5 import (  # noqa: E402
    EvidenceContext,
    RelationCandidate,
    TriggerOccurrence,
)


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _relation(
    *,
    quote: str | None = "supports",
    evidence: tuple[int | None, int | None] = (0, 18),
) -> RelationCandidate:
    return RelationCandidate(
        "supports", "e1", "e2", Decimal("1"), evidence[0], evidence[1], quote
    )


def _context(
    *,
    sentence: tuple[int, int] = (0, 18),
    clause: tuple[int, int] = (0, 18),
    occurrences: tuple[tuple[int, int], ...] = ((5, 13),),
    source_digest: str | None = None,
    occurrence_digest: str | None = None,
) -> EvidenceContext:
    source = "task supports risk"
    if source_digest is None:
        source_digest = "sha256:" + hashlib.sha256(source.encode()).hexdigest()
    if occurrence_digest is None:
        occurrence_digest = "sha256:" + hashlib.sha256(b"supports").hexdigest()
    return EvidenceContext(
        len(source),
        source_digest,
        source,
        tuple(TriggerOccurrence(start, end, occurrence_digest) for start, end in occurrences),
        sentence,
        clause,
    )


@pytest.mark.parametrize(
    ("stage", "detail", "expected"),
    [
        ("stage1", "stage-1 envelope has unbound fields", "envelope_unbound_field"),
        ("stage2", "stage-2 envelope version is not bound", "envelope_version_mismatch"),
        ("stage1", "entities[0].type is not allowlisted", "entity_candidate_invalid"),
        ("stage1", "stage-1 candidate identities must be unique", "entity_candidate_identity_duplicate"),
        ("stage1", "entities[0] exceeds source length", "entity_span_out_of_source"),
        ("stage2", "stage-2 relation attempts to mutate candidate table", "relation_endpoint_not_in_server_table"),
        ("stage2", "relations[0].evidence is invalid", "relation_evidence_invalid"),
        ("stage2", "stage-2 relation identity is invalid", "relation_candidate_invalid"),
    ],
)
def test_schema_reason_codes_cover_known_parser_boundaries(
    stage: str, detail: str, expected: str
) -> None:
    result = classify_schema_failure(stage, detail)
    assert result.code == expected
    assert result.detailAvailable is True
    assert result.code in SCHEMA_REASON_CODES


def test_unknown_schema_detail_is_sanitized_and_fail_closed() -> None:
    result = classify_schema_failure("stage1", "provider payload secret malformed at $.private")
    assert result.code == "validation_detail_unavailable"
    assert result.detailAvailable is False
    assert "provider" not in json.dumps(result.as_dict())
    assert historical_evidence_failure().code == "materializer_detail_unavailable"


def test_evidence_reason_code_family_is_finite_and_redacted() -> None:
    for code in EVIDENCE_REASON_CODES[:-1]:
        result = normalize_evidence_failure(code)
        assert result.code == code
        assert result.detailAvailable is True
    unknown = normalize_evidence_failure("source text leaked")
    assert unknown.code == "materializer_detail_unavailable"
    assert unknown.detailAvailable is False
    assert "source" not in json.dumps(unknown.as_dict())


@pytest.mark.parametrize(
    ("relation", "context", "endpoints", "expected"),
    [
        (_relation(quote=None), _context(), ((0, 4), (14, 18)), "trigger_quote_missing"),
        (_relation(evidence=(None, 18)), _context(), ((0, 4), (14, 18)), "evidence_span_missing"),
        (_relation(), None, ((0, 4), (14, 18)), "trigger_occurrence_missing"),
        (_relation(), _context(source_digest="sha256:" + "0" * 64), ((0, 4), (14, 18)), "materializer_detail_unavailable"),
        (_relation(evidence=(0, 99)), _context(), ((0, 4), (14, 18)), "evidence_span_out_of_source"),
        (_relation(), _context(sentence=(0, 5)), ((0, 4), (14, 18)), "trigger_occurrence_outside_sentence"),
        (_relation(), _context(clause=(0, 5)), ((0, 4), (14, 18)), "trigger_occurrence_outside_clause"),
        (_relation(), _context(occurrences=()), ((0, 4), (14, 18)), "trigger_occurrence_missing"),
        (_relation(), _context(occurrence_digest="sha256:" + "0" * 64), ((0, 4), (14, 18)), "trigger_quote_digest_mismatch"),
        (_relation(), _context(), ((0, 4), (14, 18)), None),
        (_relation(evidence=(0, 5)), _context(), ((0, 4), (14, 18)), "evidence_does_not_contain_trigger"),
        (_relation(), _context(), (None, (14, 18)), "evidence_does_not_contain_endpoints"),
    ],
)
def test_evidence_materializer_reason_codes_fail_closed(
    relation: RelationCandidate,
    context: EvidenceContext | None,
    endpoints: tuple[tuple[int, int] | None, tuple[int, int] | None],
    expected: str | None,
) -> None:
    result = diagnose_evidence_failure(
        relation, context=context, endpoint_spans=endpoints
    )
    assert (result.code if result is not None else None) == expected


@pytest.mark.parametrize(
    ("relation", "context", "endpoints"),
    [
        (
            SimpleNamespace(trigger_quote="supports", evidence_start="bad", evidence_end=18),
            _context(),
            ((0, 4), (14, 18)),
        ),
        (
            _relation(),
            SimpleNamespace(
                source_text="task supports risk",
                source_length=18,
                source_digest="bad",
                sentence=None,
                clause=(0, 18),
                trigger_occurrences=(),
            ),
            ((0, 4), (14, 18)),
        ),
        (
            _relation(),
            SimpleNamespace(
                source_text="task supports risk",
                source_length=18,
                source_digest="bad",
                sentence=(0, 18),
                clause="bad",
                trigger_occurrences=(),
            ),
            ((0, 4), (14, 18)),
        ),
        (
            _relation(),
            SimpleNamespace(
                source_text="task supports risk",
                source_length=18,
                source_digest="bad",
                sentence=(0, 18),
                clause=(0, 18),
                trigger_occurrences=(
                    SimpleNamespace(start="bad", end=13, quote_digest="bad"),
                ),
            ),
            ((0, 4), (14, 18)),
        ),
        (_relation(), _context(), ("bad", (14, 18))),
        (
            SimpleNamespace(trigger_quote=42, evidence_start=0, evidence_end=18),
            _context(),
            ((0, 4), (14, 18)),
        ),
    ],
)
def test_malformed_runtime_mock_fields_fail_closed(
    relation: object,
    context: object,
    endpoints: object,
) -> None:
    result = diagnose_evidence_failure(
        relation, context=context, endpoint_spans=endpoints  # type: ignore[arg-type]
    )
    assert result is not None
    assert result.code == "materializer_detail_unavailable"
    assert result.detailAvailable is False


def test_schema_rejects_unregistered_reason_codes() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    persisted = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    for section, location in (
        ("schema", ("totals", "schemaReasonCounts")),
        ("evidence", ("totals", "evidenceReasonCounts")),
        ("bucket", ("totals", "evidenceBucketCounts")),
    ):
        candidate = json.loads(json.dumps(persisted))
        candidate[location[0]][location[1]]["unknown_not_registered"] = 1
        errors = list(Draft202012Validator(schema).iter_errors(candidate))
        assert errors, section


def test_rm30_report_matches_schema_and_historical_counts_without_mutation() -> None:
    before = _digest(REPORT)
    generated = build_from_historical_report()
    persisted = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(persisted)) == []
    assert generated == persisted
    assert persisted["accounting"] == {
        "providerCallsAttempted": 144,
        "retryCount": 0,
        "schemaInvalid": 6,
        "invalidEvidence": 17,
        "schemaFailureReconciled": True,
        "evidenceFailureReconciled": True,
    }
    assert persisted["arms"]["predicted-entities"]["schemaReasonCounts"] == {
        "validation_detail_unavailable": 5
    }
    assert persisted["arms"]["gold-entities"]["evidenceReasonCounts"] == {
        "materializer_detail_unavailable": 17
    }
    assert persisted["arms"]["gold-relations"]["invalidEvidence"] == 0
    assert persisted["redaction"] == {
        "rawProviderPayloadIncluded": False,
        "rawSourceTextIncluded": False,
        "rawValidationDetailIncluded": False,
        "rawTriggerQuoteIncluded": False,
    }
    assert _digest(REPORT) == before


def test_rm30_package_has_no_unbound_digest_or_execution_scope() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    assert all(value != "TO_BE_BOUND" for value in package["boundDigests"].values())
    assert package["governance"]["offlineImplementationAuthorized"] is True
    for key in (
        "providerExecutionAuthorized",
        "supersedingLineagePreparationAuthorized",
        "preregistrationIssued",
        "technicalFreezeIssued",
        "newAuthorizationIssued",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        assert package["governance"][key] is False
