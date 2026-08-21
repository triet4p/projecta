"""RM-30 offline diagnostic remediation.

This module is a versioned, provider-neutral diagnostic boundary.  It may read
runtime-only source while classifying an offline mock relation, but every
returned record is finite and sanitized: no source, payload, raw validation
message or trigger quote is returned.  It is intentionally not imported by the
guarded live runner.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_REPORT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
HISTORICAL_REPORT_DIGEST = (
    "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
)

SCHEMA_REASON_CODES = (
    "envelope_unbound_field",
    "envelope_version_mismatch",
    "entity_candidate_invalid",
    "entity_candidate_identity_duplicate",
    "entity_span_out_of_source",
    "relation_candidate_invalid",
    "relation_endpoint_not_in_server_table",
    "relation_evidence_invalid",
    "validation_detail_unavailable",
)

EVIDENCE_REASON_CODES = (
    "trigger_quote_missing",
    "trigger_quote_digest_mismatch",
    "trigger_occurrence_missing",
    "trigger_occurrence_outside_sentence",
    "trigger_occurrence_outside_clause",
    "evidence_span_missing",
    "evidence_span_out_of_source",
    "evidence_does_not_contain_trigger",
    "evidence_does_not_contain_endpoints",
    "materializer_detail_unavailable",
)


@dataclass(frozen=True, slots=True)
class SanitizedReason:
    """Finite public reason; raw detail is deliberately not retained."""

    code: str
    detailAvailable: bool

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "detailAvailable": self.detailAvailable}


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _require_stage(stage: str) -> None:
    if stage not in {"stage1", "stage2"}:
        raise ValueError("stage must be stage1 or stage2")


def classify_schema_failure(stage: str, raw_detail: str | None) -> SanitizedReason:
    """Map known parser boundaries to finite codes without exposing detail."""

    _require_stage(stage)
    if not raw_detail:
        return SanitizedReason("validation_detail_unavailable", False)
    detail = raw_detail.lower()
    if "unbound fields" in detail:
        return SanitizedReason("envelope_unbound_field", True)
    if "version is not bound" in detail:
        return SanitizedReason("envelope_version_mismatch", True)
    if stage == "stage1":
        if "candidate identities must be unique" in detail:
            return SanitizedReason("entity_candidate_identity_duplicate", True)
        if "exceeds source length" in detail:
            return SanitizedReason("entity_span_out_of_source", True)
        if "allowlisted" in detail or "candidate" in detail:
            return SanitizedReason("entity_candidate_invalid", True)
    else:
        if "invalid candidate" in detail or "candidate table" in detail:
            return SanitizedReason("relation_endpoint_not_in_server_table", True)
        if "evidence" in detail:
            return SanitizedReason("relation_evidence_invalid", True)
        if "relation" in detail or "relations" in detail:
            return SanitizedReason("relation_candidate_invalid", True)
    return SanitizedReason("validation_detail_unavailable", False)


def historical_schema_failure(stage: str) -> SanitizedReason:
    """Classify a sanitized historical failure without inventing its cause."""

    return classify_schema_failure(stage, None)


def normalize_evidence_failure(raw_reason: str | None) -> SanitizedReason:
    """Normalize a materializer reason and discard all unregistered detail."""

    if raw_reason in EVIDENCE_REASON_CODES and raw_reason != "materializer_detail_unavailable":
        return SanitizedReason(str(raw_reason), True)
    return SanitizedReason("materializer_detail_unavailable", False)


def historical_evidence_failure() -> SanitizedReason:
    return normalize_evidence_failure(None)


def _valid_span(span: tuple[int, int], source_length: int) -> bool:
    return 0 <= span[0] < span[1] <= source_length


def diagnose_evidence_failure(
    relation: Any,
    *,
    context: Any | None,
    endpoint_spans: tuple[tuple[int, int] | None, tuple[int, int] | None],
) -> SanitizedReason | None:
    """Return the first deterministic evidence rejection, or ``None``.

    ``context`` is expected to be the runtime-only v5 EvidenceContext shape.
    The result never contains source text, offsets or the trigger quote.
    """

    if getattr(relation, "trigger_quote", None) in (None, ""):
        return normalize_evidence_failure("trigger_quote_missing")
    evidence_start = getattr(relation, "evidence_start", None)
    evidence_end = getattr(relation, "evidence_end", None)
    if evidence_start is None or evidence_end is None:
        return normalize_evidence_failure("evidence_span_missing")
    if context is None:
        return normalize_evidence_failure("trigger_occurrence_missing")
    source_text = getattr(context, "source_text", None)
    source_length = getattr(context, "source_length", None)
    if not isinstance(source_text, str) or not isinstance(source_length, int):
        return normalize_evidence_failure("materializer_detail_unavailable")
    if len(source_text) != source_length:
        return normalize_evidence_failure("materializer_detail_unavailable")
    source_digest = getattr(context, "source_digest", None)
    expected_source_digest = "sha256:" + hashlib.sha256(source_text.encode()).hexdigest()
    if source_digest != expected_source_digest:
        return normalize_evidence_failure("materializer_detail_unavailable")
    evidence_span = (int(evidence_start), int(evidence_end))
    if not _valid_span(evidence_span, source_length):
        return normalize_evidence_failure("evidence_span_out_of_source")
    sentence = tuple(getattr(context, "sentence", ()))
    clause = tuple(getattr(context, "clause", ()))
    if len(sentence) != 2 or not _valid_span((int(sentence[0]), int(sentence[1])), source_length):
        return normalize_evidence_failure("trigger_occurrence_outside_sentence")
    if len(clause) != 2 or not _valid_span((int(clause[0]), int(clause[1])), source_length):
        return normalize_evidence_failure("trigger_occurrence_outside_clause")
    quote = str(relation.trigger_quote)
    occurrences = tuple(getattr(context, "trigger_occurrences", ()))
    if not occurrences:
        return normalize_evidence_failure("trigger_occurrence_missing")
    quote_match = False
    for occurrence in occurrences:
        occurrence_span = (int(occurrence.start), int(occurrence.end))
        if not _valid_span(occurrence_span, source_length):
            continue
        source_slice = source_text[occurrence_span[0] : occurrence_span[1]]
        expected_quote_digest = "sha256:" + hashlib.sha256(source_slice.encode()).hexdigest()
        if source_slice != quote or occurrence.quote_digest != expected_quote_digest:
            continue
        quote_match = True
        if not (sentence[0] <= occurrence_span[0] and occurrence_span[1] <= sentence[1]):
            return normalize_evidence_failure("trigger_occurrence_outside_sentence")
        if not (clause[0] <= occurrence_span[0] and occurrence_span[1] <= clause[1]):
            return normalize_evidence_failure("trigger_occurrence_outside_clause")
        if not (evidence_span[0] <= occurrence_span[0] and occurrence_span[1] <= evidence_span[1]):
            return normalize_evidence_failure("evidence_does_not_contain_trigger")
    if not quote_match:
        return normalize_evidence_failure("trigger_quote_digest_mismatch")
    source_span, target_span = endpoint_spans
    if (
        source_span is None
        or target_span is None
        or not _valid_span(source_span, source_length)
        or not _valid_span(target_span, source_length)
        or not (evidence_span[0] <= source_span[0] and source_span[1] <= evidence_span[1])
        or not (evidence_span[0] <= target_span[0] and target_span[1] <= evidence_span[1])
    ):
        return normalize_evidence_failure("evidence_does_not_contain_endpoints")
    return None


def _historical_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    records = list(report["caseRecords"])
    schema_counts: Counter[str] = Counter()
    schema_reason_counts: Counter[str] = Counter()
    arm_schema_reason_counts: dict[str, Counter[str]] = {
        arm: Counter()
        for arm in ("predicted-entities", "gold-entities", "gold-relations")
    }
    evidence_counts: Counter[str] = Counter()
    evidence_reason_counts: Counter[str] = Counter()
    arm_evidence_reason_counts: dict[str, Counter[str]] = {
        arm: Counter()
        for arm in ("predicted-entities", "gold-entities", "gold-relations")
    }
    arm_schema: dict[str, dict[str, int]] = {
        arm: {"stage1": 0, "stage2": 0}
        for arm in ("predicted-entities", "gold-entities", "gold-relations")
    }
    arm_evidence: Counter[str] = Counter()
    for record in records:
        for arm in arm_schema:
            for stage in ("stage1", "stage2"):
                item = record["arms"][arm][stage]
                if item["responseReceived"] and not item["schemaValid"]:
                    arm_schema[arm][stage] += 1
                    schema_counts[f"{arm}:{stage}"] += 1
                    reason = historical_schema_failure(stage)
                    schema_reason_counts[reason.code] += 1
                    arm_schema_reason_counts[arm][reason.code] += 1
            invalid_evidence = int(record["arms"][arm]["invalidEvidenceCount"])
            if invalid_evidence:
                arm_evidence[arm] += invalid_evidence
                evidence_counts["unsupported"] += invalid_evidence
                reason = historical_evidence_failure()
                evidence_reason_counts[reason.code] += invalid_evidence
                arm_evidence_reason_counts[arm][reason.code] += invalid_evidence
    schema_total = sum(schema_counts.values())
    evidence_total = sum(evidence_counts.values())
    accounting = report["accounting"]
    return {
        "accounting": {
            "providerCallsAttempted": int(accounting["providerCallsAttempted"]),
            "retryCount": int(accounting["retryCount"]),
            "schemaInvalid": schema_total,
            "invalidEvidence": evidence_total,
            "schemaFailureReconciled": schema_total == int(accounting["failureClasses"]["schemaInvalid"]),
            "evidenceFailureReconciled": evidence_total == 17,
        },
        "arms": {
            arm: {
                "schemaInvalid": arm_schema[arm],
                "schemaReasonCounts": dict(arm_schema_reason_counts[arm])
                if arm_schema[arm]["stage1"] or arm_schema[arm]["stage2"]
                else {},
                "invalidEvidence": arm_evidence[arm],
                "evidenceReasonCounts": dict(arm_evidence_reason_counts[arm])
                if arm_evidence[arm]
                else {},
            }
            for arm in arm_schema
        },
        "totals": {
            "schemaInvalid": schema_total,
            "schemaReasonCounts": dict(schema_reason_counts),
            "invalidEvidence": evidence_total,
            "evidenceBucketCounts": dict(evidence_counts),
            "evidenceReasonCounts": dict(evidence_reason_counts),
            "goldRelationsControlFailures": arm_evidence["gold-relations"],
        },
        "redaction": {
            "rawProviderPayloadIncluded": False,
            "rawSourceTextIncluded": False,
            "rawValidationDetailIncluded": False,
            "rawTriggerQuoteIncluded": False,
        },
    }


def build_offline_diagnostic_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Produce the versioned sanitized report for an offline historical input."""

    summary = _historical_summary(report)
    return {
        "artifactVersion": "s12.s12-f-12.rm30-offline-diagnostic-report.v1",
        "status": "OFFLINE_DIAGNOSTIC_REPORT_READY_PENDING_OWNER_REVIEW",
        "experimentId": "s12-f-12",
        "sourceReport": {
            "path": HISTORICAL_REPORT.relative_to(ROOT).as_posix(),
            "digest": HISTORICAL_REPORT_DIGEST,
            "historicalResultsPreserved": True,
        },
        **summary,
        "unknownPolicy": {
            "historicalSchemaReason": "validation_detail_unavailable",
            "historicalEvidenceReason": "materializer_detail_unavailable",
            "unknownIsPass": False,
        },
        "governance": {
            "offlineOnly": True,
            "providerCalls": 0,
            "providerExecutionAuthorized": False,
            "supersedingLineagePreparationAuthorized": False,
            "preregistrationIssued": False,
            "technicalFreezeIssued": False,
            "newAuthorizationIssued": False,
            "validationAccessAuthorized": False,
            "heldOutAccessAuthorized": False,
            "stageBAuthorized": False,
            "candidateSelectionAuthorized": False,
            "promotionAuthorized": False,
        },
    }


def build_from_historical_report(path: Path = HISTORICAL_REPORT) -> dict[str, Any]:
    if digest(path) != HISTORICAL_REPORT_DIGEST:
        raise ValueError("RM-30 refuses a changed historical report")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise TypeError("historical report must be an object")
    return build_offline_diagnostic_report(report)


if __name__ == "__main__":
    print(json.dumps(build_from_historical_report(), indent=2, sort_keys=True))
