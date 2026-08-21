"""RM-50 Option A: closed, finite offline diagnostic/report contract.

This module consumes only the immutable sanitized v6/v9 reports.  It does not
import or modify a live runner, read provider payloads, reconstruct source, or
prepare a new execution lineage.  Its public report is intentionally finite;
unknown reasons and malformed count maps fail closed.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from decimal import Decimal

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
V6_PATH = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
V9_PATH = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json"
SCHEMA_PATH = ROOT / "evaluation/sprint-12/harness/s12-f-12-rm50-offline-diagnostic-report.schema.v1.json"
REPORT_PATH = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm50-offline-diagnostic-report.v1.json"

V6_DIGEST = "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
V9_DIGEST = "sha256:84cb0667b8ee3469be5bdd4c3545a41012ba46bb07071508c41dca76fbf3761e"

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
ARMS = ("predicted-entities", "gold-entities", "gold-relations")
STAGES = ("stage1", "stage2")
RAW_KEY_ALIASES = (
    "raw",
    "payload",
    "sourcetext",
    "triggerquote",
    "validationdetail",
    "providerresponse",
    "evidencetext",
)
ALLOWED_POLICY_KEYS = {
    "rawdatapolicy",
    "rawproviderpayloadincluded",
    "rawsourcetextincluded",
    "rawtriggerquoteincluded",
    "rawvalidationdetailincluded",
    "recursivedynamickeyrawdataexclusion",
    "reproducedwithoutproviderorrawreconstruction",
}
ALLOWED_REASON_KEYS = set(SCHEMA_REASON_CODES) | set(EVIDENCE_REASON_CODES)


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, expected: str) -> dict[str, Any]:
    if digest(path) != expected:
        raise ValueError(f"immutable report digest mismatch: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("historical report must be an object")
    return value


def _finite_counts(value: Mapping[str, Any], allowed: tuple[str, ...]) -> dict[str, int]:
    if set(value) - set(allowed):
        raise ValueError("unknown diagnostic reason code")
    result: dict[str, int] = {}
    for code in allowed:
        count = value.get(code, 0)
        if type(count) is not int or count < 0:
            raise ValueError("diagnostic counts must be non-negative integers")
        result[code] = count
    return result


def normalize_schema_counts(value: Mapping[str, Any]) -> dict[str, int]:
    return _finite_counts(value, SCHEMA_REASON_CODES)


def normalize_evidence_counts(value: Mapping[str, Any]) -> dict[str, int]:
    return _finite_counts(value, EVIDENCE_REASON_CODES)


def classify_unknown_schema() -> str:
    return "validation_detail_unavailable"


def classify_unknown_evidence() -> str:
    return "materializer_detail_unavailable"


def _case_run(case: Mapping[str, Any]) -> str:
    return f"{case['caseId']}#run-{case['runId']}"


def _schema_clusters(report: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for case in report["caseRecords"]:
        for arm in ARMS:
            for stage in STAGES:
                item = case["arms"][arm].get(stage, {})
                if isinstance(item, Mapping) and item.get("failureClass"):
                    result.setdefault(f"{arm}/{stage}", []).append(_case_run(case))
    return result


def _evidence_clusters(report: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for case in report["caseRecords"]:
        for arm in ARMS:
            count = int(case["arms"][arm].get("invalidEvidenceCount", 0))
            if count:
                result.setdefault(arm, []).extend([_case_run(case)] * count)
    return result


def _set_cluster_delta(left: Mapping[str, list[str]], right: Mapping[str, list[str]]) -> dict[str, Any]:
    keys = sorted(set(left) | set(right))
    by_key: dict[str, Any] = {}
    for key in keys:
        old = set(left.get(key, ()))
        new = set(right.get(key, ()))
        by_key[key] = {
            "v6Count": len(left.get(key, ())),
            "v9Count": len(right.get(key, ())),
            "overlap": sorted(old & new),
            "newInV9": sorted(new - old),
            "resolvedFromV6": sorted(old - new),
        }
    return by_key


def _reason_totals(report: Mapping[str, Any], field: str, allowed: tuple[str, ...]) -> dict[str, int]:
    result: Counter[str] = Counter()
    for case in report["caseRecords"]:
        for arm in ARMS:
            diagnostics = case["arms"][arm].get("diagnostics", {})
            result.update(diagnostics.get(field, {}))
    return _finite_counts(result, allowed)


def _source_summary(report: Mapping[str, Any], *, historical_unknowns: bool) -> dict[str, Any]:
    """Derive all failure totals from case records and reconcile accounting."""

    schema_clusters = _schema_clusters(report)
    evidence_clusters = _evidence_clusters(report)
    schema_total = sum(len(values) for values in schema_clusters.values())
    evidence_total = sum(len(values) for values in evidence_clusters.values())
    accounting = report.get("accounting")
    if not isinstance(accounting, Mapping):
        raise ValueError("source accounting is missing")
    failure_classes = accounting.get("failureClasses")
    if not isinstance(failure_classes, Mapping):
        raise ValueError("source failure classes are missing")
    if schema_total != failure_classes.get("schemaInvalid"):
        raise ValueError("source schema-invalid total does not reconcile")
    diagnostics_schema: dict[str, int]
    diagnostics_evidence: dict[str, int]
    if historical_unknowns:
        diagnostics_schema = {code: 0 for code in SCHEMA_REASON_CODES}
        diagnostics_schema["validation_detail_unavailable"] = schema_total
        diagnostics_evidence = {code: 0 for code in EVIDENCE_REASON_CODES}
        diagnostics_evidence["materializer_detail_unavailable"] = evidence_total
    else:
        diagnostics_schema = _reason_totals(report, "schemaReasonCounts", SCHEMA_REASON_CODES)
        diagnostics_evidence = _reason_totals(report, "evidenceReasonCounts", EVIDENCE_REASON_CODES)
        if sum(diagnostics_schema.values()) != schema_total:
            raise ValueError("source schema diagnostic reasons do not reconcile")
        if sum(diagnostics_evidence.values()) != evidence_total:
            raise ValueError("source evidence diagnostic reasons do not reconcile")
    for case in report["caseRecords"]:
        for arm in ARMS:
            item = case["arms"][arm]
            invalid_evidence = item.get("invalidEvidenceCount", 0)
            if type(invalid_evidence) is not int or invalid_evidence < 0:
                raise ValueError("source invalidEvidenceCount must be a non-negative integer")
            reasons = item.get("diagnostics", {}).get("evidenceReasonCounts", {})
            if reasons and sum(normalize_evidence_counts(reasons).values()) != invalid_evidence:
                raise ValueError("source case evidence reasons do not reconcile")
    return {
        "schemaClusters": schema_clusters,
        "evidenceClusters": evidence_clusters,
        "schemaTotal": schema_total,
        "evidenceTotal": evidence_total,
        "schemaReasons": diagnostics_schema,
        "evidenceReasons": diagnostics_evidence,
        "accounting": accounting,
    }


def assert_no_raw_data_aliases(value: Any, *, path: str = "$", allow_policy_keys: bool = False) -> None:
    """Reject raw-data aliases recursively, including arbitrary dynamic keys."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if not (allow_policy_keys and (normalized in ALLOWED_POLICY_KEYS or str(key) in ALLOWED_REASON_KEYS)):
                if any(alias in normalized for alias in RAW_KEY_ALIASES):
                    raise ValueError(f"raw-data alias at {path}.{key}")
            assert_no_raw_data_aliases(child, path=f"{path}.{key}", allow_policy_keys=allow_policy_keys)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_raw_data_aliases(child, path=f"{path}[{index}]", allow_policy_keys=allow_policy_keys)


def _slice_transition(v6: Mapping[str, Any], v9: Mapping[str, Any]) -> dict[str, Any]:
    def j1(arm: str, report: Mapping[str, Any]) -> Mapping[str, Any]:
        slice_record = next(item for item in report["sliceRecords"] if item["label"] == "J1")
        return slice_record["metrics"]["arms"][arm]["relation"]["evidence"]

    old = j1("gold-entities", v6)
    new = j1("gold-entities", v9)
    if old["supportRate"] != "not-applicable" or old["exactRate"] != "not-applicable":
        raise ValueError("expected v6 J1/gold-entities evidence to be not-applicable")
    if new["supportRate"] != 0.0 or new["exactRate"] != 0.0:
        raise ValueError("expected v9 J1/gold-entities evidence to be 0.0")
    return {
        "slice": "J1",
        "arm": "gold-entities",
        "supportRate": {"v6": "not-applicable", "v9": 0.0, "transition": "not-applicable_to_zero"},
        "exactRate": {"v6": "not-applicable", "v9": 0.0, "transition": "not-applicable_to_zero"},
        "interpretation": "This is an explicit registered denominator transition, not a causal or quality claim.",
    }


def build_report(v6: Mapping[str, Any] | None = None, v9: Mapping[str, Any] | None = None) -> dict[str, Any]:
    v6 = v6 or _load(V6_PATH, V6_DIGEST)
    v9 = v9 or _load(V9_PATH, V9_DIGEST)
    summary6 = _source_summary(v6, historical_unknowns=True)
    summary9 = _source_summary(v9, historical_unknowns=False)
    account6 = summary6["accounting"]
    account9 = summary9["accounting"]
    if int(account6["providerCallsAttempted"]) != int(account9["providerCallsAttempted"]):
        raise ValueError("source provider call counts differ")
    if int(account6["retryCount"]) != 0 or int(account9["retryCount"]) != 0:
        raise ValueError("source retry count is not zero")
    cost_delta = Decimal(str(account9["totalCostUsd"])) - Decimal(str(account6["totalCostUsd"]))
    report: dict[str, Any] = {
        "artifactVersion": "s12.s12-f-12.rm50-offline-diagnostic-report.v1",
        "status": "OFFLINE_DIAGNOSTIC_CONTRACT_HARDENED_PENDING_OWNER_REVIEW",
        "experimentId": "s12-f-12",
        "taskId": "S12-RM-50",
        "sourceReports": {
            "v6": {"path": V6_PATH.relative_to(ROOT).as_posix(), "digest": V6_DIGEST, "immutable": True},
            "v9": {"path": V9_PATH.relative_to(ROOT).as_posix(), "digest": V9_DIGEST, "immutable": True},
        },
        "accounting": {
            "v6": {"providerCalls": int(account6["providerCallsAttempted"]), "responses": int(account6["responsesReceived"]), "retryCount": int(account6["retryCount"]), "schemaInvalid": summary6["schemaTotal"], "invalidEvidence": summary6["evidenceTotal"], "costUsd": str(account6["totalCostUsd"])},
            "v9": {"providerCalls": int(account9["providerCallsAttempted"]), "responses": int(account9["responsesReceived"]), "retryCount": int(account9["retryCount"]), "schemaInvalid": summary9["schemaTotal"], "invalidEvidence": summary9["evidenceTotal"], "costUsd": str(account9["totalCostUsd"])},
            "reconciled": True,
            "deltaV9MinusV6": {"schemaInvalid": summary9["schemaTotal"] - summary6["schemaTotal"], "invalidEvidence": summary9["evidenceTotal"] - summary6["evidenceTotal"], "costUsd": f"{cost_delta:.8f}"},
        },
        "diagnostics": {
            "schemaReasonCounts": {"v6": summary6["schemaReasons"], "v9": summary9["schemaReasons"]},
            "evidenceReasonCounts": {"v6": summary6["evidenceReasons"], "v9": summary9["evidenceReasons"]},
            "schemaClusterDelta": _set_cluster_delta(summary6["schemaClusters"], summary9["schemaClusters"]),
            "evidenceClusterDelta": _set_cluster_delta(summary6["evidenceClusters"], summary9["evidenceClusters"]),
            "totalsReconciled": True,
        },
        "sliceTransitions": {"J1GoldEntitiesEvidence": _slice_transition(v6, v9)},
        "rawDataPolicy": {
            "rawProviderPayloadIncluded": False,
            "rawSourceTextIncluded": False,
            "rawTriggerQuoteIncluded": False,
            "rawValidationDetailIncluded": False,
            "recursiveDynamicKeyExclusion": True,
        },
        "unknownPolicy": {
            "unknownSchemaReason": "validation_detail_unavailable",
            "unknownEvidenceReason": "materializer_detail_unavailable",
            "unknownIsPass": False,
        },
        "stopCriteria": {
            "closedFiniteReasonAllowLists": True,
            "exactCountReconciliation": True,
            "unknownFailClosed": True,
            "recursiveDynamicKeyRawDataExclusion": True,
            "j1GoldEntitiesTransitionRecorded": True,
            "allPassed": True,
        },
        "governance": {
            "offlineOnly": True,
            "providerCalls": 0,
            "runtimeRemediationAuthorized": False,
            "supersedingLineagePreparationAuthorized": False,
            "preregistrationIssued": False,
            "technicalFreezeIssued": False,
            "newAuthorizationIssued": False,
            "providerExecutionAuthorized": False,
            "validationAccessAuthorized": False,
            "heldOutAccessAuthorized": False,
            "stageBAuthorized": False,
            "candidateSelectionAuthorized": False,
            "promotionAuthorized": False,
        },
        "nextGate": "S12-RM-51_OWNER_REVIEW_RM50_OFFLINE_DIAGNOSTICS_AND_PARITY_FIXTURES",
    }
    assert_no_raw_data_aliases(report, allow_policy_keys=True)
    return report


def validate_report(report: Mapping[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda error: list(error.path))
    if errors:
        raise ValueError("RM-50 report schema invalid: " + "; ".join(error.message for error in errors))
    expected = build_report()
    if dict(report) != expected:
        raise ValueError("RM-50 diagnostic report does not match regenerated immutable-source analysis")
    assert_no_raw_data_aliases(report, allow_policy_keys=True)
    for arm_counts in report["diagnostics"]["schemaReasonCounts"].values():
        normalize_schema_counts(arm_counts)
    for arm_counts in report["diagnostics"]["evidenceReasonCounts"].values():
        normalize_evidence_counts(arm_counts)


def main() -> None:
    report = build_report()
    validate_report(report)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
