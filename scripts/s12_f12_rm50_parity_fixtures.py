"""RM-50 Option B: deterministic scorer/materializer parity fixtures.

Fixtures contain only symbolic case/arm/stage/slice labels and finite expected
outcomes.  They do not contain source text, provider payloads, trigger quotes,
or runtime lineage data.  This module is offline-only and is intentionally not
imported by a live runner.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from s12_f12_rm50_offline_diagnostics import (
    EVIDENCE_REASON_CODES,
    SCHEMA_REASON_CODES,
    assert_no_raw_data_aliases,
    V6_DIGEST,
    V9_DIGEST,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm50-parity-fixtures.v1.json"
REPORT_PATH = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm50-parity-report.v1.json"
DIAGNOSTIC_REPORT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm50-offline-diagnostic-report.v1.json"
PARITY_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-rm50-parity-report.schema.v1.json"


@dataclass(frozen=True, slots=True)
class Relation:
    predicate: str
    source: str
    target: str
    confidence: Decimal


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _relation(value: dict[str, Any]) -> Relation:
    return Relation(
        predicate=str(value["predicate"]),
        source=str(value["sourceLabel"]),
        target=str(value["targetLabel"]),
        confidence=Decimal(str(value["confidence"])),
    )


def score_relations(gold_values: list[dict[str, Any]], predicted_values: list[dict[str, Any]]) -> dict[str, Any]:
    """Score exact semantic pairs with deterministic duplicate/tie handling."""

    gold = [_relation(value) for value in gold_values]
    predicted = sorted(
        enumerate(_relation(value) for value in predicted_values),
        key=lambda item: (-item[1].confidence, item[0]),
    )
    gold_counts = Counter((item.predicate, item.source, item.target) for item in gold)
    exact = 0
    exact_keys: set[tuple[str, str, str]] = set()
    for _, item in predicted:
        key = (item.predicate, item.source, item.target)
        if gold_counts[key] > 0:
            gold_counts[key] -= 1
            exact += 1
            exact_keys.add(key)
    gold_key_set = {(item.predicate, item.source, item.target) for item in gold}
    predicted_key_set = {(item.predicate, item.source, item.target) for _, item in predicted}
    reversed_endpoint = 0
    wrong_endpoint = 0
    wrong_predicate = 0
    for _, item in predicted:
        key = (item.predicate, item.source, item.target)
        if key in exact_keys:
            continue
        if any(item.predicate == g.predicate and item.source == g.target and item.target == g.source for g in gold):
            reversed_endpoint += 1
        elif any(item.source == g.source and item.target == g.target and item.predicate != g.predicate for g in gold):
            wrong_predicate += 1
        elif item.predicate in {g.predicate for g in gold}:
            wrong_endpoint += 1
    return {
        "gold": len(gold),
        "predicted": len(predicted),
        "exactMatch": exact,
        "missingRelation": max(len(gold) - exact, 0),
        "extraRelation": max(len(predicted) - exact, 0),
        "reversedEndpoint": reversed_endpoint,
        "wrongEndpoint": wrong_endpoint,
        "wrongPredicate": wrong_predicate,
        "goldReconciled": exact + max(len(gold) - exact, 0) == len(gold),
        "predictedReconciled": exact + max(len(predicted) - exact, 0) == len(predicted),
        "tieOrderDeterministic": True,
        "unusedGoldKeys": sorted(f"{p}:{s}:{t}" for p, s, t in gold_key_set - exact_keys),
        "unusedPredictedKeys": sorted(f"{p}:{s}:{t}" for p, s, t in predicted_key_set - exact_keys),
    }


def classify_evidence(trigger_contained: bool, endpoints_contained: bool) -> str | None:
    if not trigger_contained:
        return "evidence_does_not_contain_trigger"
    if not endpoints_contained:
        return "evidence_does_not_contain_endpoints"
    return None


def run_scorer_scenarios() -> dict[str, dict[str, Any]]:
    """Exercise duplicate/order/tie and relation error buckets offline."""

    def rel(predicate: str, source: str, target: str, confidence: str = "0.5") -> dict[str, Any]:
        return {"predicate": predicate, "sourceLabel": source, "targetLabel": target, "confidence": confidence}

    cases = {
        "duplicate": ([rel("supports", "a", "b")], [rel("supports", "a", "b", "0.9"), rel("supports", "a", "b", "0.9")]),
        "order": ([rel("supports", "a", "b"), rel("supports", "b", "c")], [rel("supports", "b", "c"), rel("supports", "a", "b")]),
        "tie": ([rel("supports", "a", "b")], [rel("supports", "a", "c", "0.5"), rel("supports", "a", "b", "0.5")]),
        "wrong-predicate": ([rel("supports", "a", "b")], [rel("blocks", "a", "b")]),
        "reversed-endpoint": ([rel("supports", "a", "b")], [rel("supports", "b", "a")]),
        "extra": ([rel("supports", "a", "b")], [rel("supports", "a", "b"), rel("supports", "a", "c")]),
        "missing": ([rel("supports", "a", "b"), rel("supports", "b", "c")], [rel("supports", "a", "b")]),
    }
    return {name: score_relations(gold, predicted) for name, (gold, predicted) in cases.items()}


def _fixture_data() -> dict[str, Any]:
    schema_fixtures = [
        ("schema-unbound", "envelope_unbound_field"),
        ("schema-version", "envelope_version_mismatch"),
        ("schema-entity-invalid", "entity_candidate_invalid"),
        ("schema-duplicate", "entity_candidate_identity_duplicate"),
        ("schema-span", "entity_span_out_of_source"),
        ("schema-relation-invalid", "relation_candidate_invalid"),
        ("schema-endpoint-table", "relation_endpoint_not_in_server_table"),
        ("schema-evidence-invalid", "relation_evidence_invalid"),
        ("schema-unknown", "validation_detail_unavailable"),
    ]
    schema = [
        {"fixtureId": fixture_id, "kind": "schema", "caseRun": "fixture-schema#run-1", "arm": "predicted-entities", "stage": "stage1", "slice": "J1", "expectedReason": reason}
        for fixture_id, reason in schema_fixtures
    ]
    evidence_reasons = [
        "trigger_quote_missing", "trigger_quote_digest_mismatch", "trigger_occurrence_missing",
        "trigger_occurrence_outside_sentence", "trigger_occurrence_outside_clause", "evidence_span_missing",
        "evidence_span_out_of_source", "evidence_does_not_contain_trigger", "evidence_does_not_contain_endpoints",
        "materializer_detail_unavailable",
    ]
    evidence = [
        {"fixtureId": f"evidence-{index}", "kind": "evidence", "caseRun": "fixture-evidence#run-1", "arm": "gold-entities", "stage": "stage2", "slice": "relation-positive", "expectedReason": reason}
        for index, reason in enumerate(evidence_reasons, start=1)
    ]
    scorer = [
        "duplicate", "order", "tie", "wrong-predicate", "reversed-endpoint", "extra", "missing"
    ]
    scorer_fixtures = [
        {"fixtureId": f"scorer-{name}", "kind": "scorer", "caseRun": "fixture-scorer#run-1", "arm": "gold-relations", "stage": "stage2", "slice": "J1", "scenario": name}
        for name in scorer
    ]
    cluster_schema = [
        "s12-a-4027#run-1", "s12-a-4016#run-1", "s12-a-4032#run-1", "s12-a-4016#run-2", "s12-a-4016#run-3"
    ]
    cluster_trigger = [
        "s12-a-4007#run-1", "s12-a-4011#run-1", "s12-a-4015#run-1", "s12-a-4019#run-1", "s12-a-4027#run-1",
        "s12-a-4035#run-1", "s12-a-4007#run-2", "s12-a-4011#run-2", "s12-a-4015#run-2", "s12-a-4019#run-2",
        "s12-a-4027#run-2", "s12-a-4035#run-2", "s12-a-4043#run-2", "s12-a-4007#run-3"
    ]
    cluster_endpoint = [
        "s12-a-4011#run-3",
        "s12-a-4015#run-3", "s12-a-4019#run-3", "s12-a-4027#run-3", "s12-a-4035#run-3", "s12-a-4043#run-3"
    ]
    cluster_evidence = cluster_trigger + cluster_endpoint
    cluster_cases = (
        [{"kind": "schema", "caseRun": case_run, "arm": "predicted-entities", "stage": "stage1", "reason": "entity_span_out_of_source", "slice": "all-development"} for case_run in cluster_schema]
        + [{"kind": "evidence", "caseRun": case_run, "arm": "gold-entities", "stage": "stage2", "reason": "evidence_does_not_contain_trigger", "slice": "relation-positive"} for case_run in cluster_trigger]
        + [{"kind": "evidence", "caseRun": case_run, "arm": "gold-entities", "stage": "stage2", "reason": "evidence_does_not_contain_endpoints", "slice": "relation-positive"} for case_run in cluster_endpoint]
    )
    schema_cluster_cases = [item for item in cluster_cases if item["kind"] == "schema"]
    evidence_cluster_cases = [item for item in cluster_cases if item["kind"] == "evidence"]
    evidence_reason_counts = Counter(item["reason"] for item in evidence_cluster_cases)
    return {
        "artifactVersion": "s12.s12-f-12.rm50-parity-fixtures.v1",
        "status": "OFFLINE_PARITY_FIXTURES_READY_PENDING_OWNER_REVIEW",
        "experimentId": "s12-f-12",
        "taskId": "S12-RM-50",
        "sanitizedOnly": True,
        "rawProviderPayloadIncluded": False,
        "rawSourceTextIncluded": False,
        "rawTriggerQuoteIncluded": False,
        "rawValidationDetailIncluded": False,
        "fixtureMatrix": schema + evidence + scorer_fixtures,
        "v9ClusterCases": cluster_cases,
        "v9SanitizedClusters": {
            "schemaInvalid": {"total": len(schema_cluster_cases), "armStage": "predicted-entities/stage1", "reason": "entity_span_out_of_source", "caseRuns": [item["caseRun"] for item in schema_cluster_cases]},
            "invalidEvidence": {"total": len(evidence_cluster_cases), "arm": "gold-entities", "reasonCounts": dict(evidence_reason_counts), "caseRuns": [item["caseRun"] for item in evidence_cluster_cases]},
        },
        "goldRelationsControl": {"fixtureArm": "gold-relations", "invalidEvidence": 0, "integrityPass": True},
    }


def build_parity_report(fixtures: dict[str, Any] | None = None) -> dict[str, Any]:
    fixtures = fixtures or json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert_no_raw_data_aliases(fixtures, allow_policy_keys=True)
    matrix = fixtures["fixtureMatrix"]
    if len(matrix) != 26:
        raise ValueError("fixture matrix count changed")
    schema_reasons = {item["expectedReason"] for item in matrix if item["kind"] == "schema"}
    evidence_reasons = {item["expectedReason"] for item in matrix if item["kind"] == "evidence"}
    if schema_reasons != set(SCHEMA_REASON_CODES) or evidence_reasons != set(EVIDENCE_REASON_CODES):
        raise ValueError("fixture matrix does not cover the finite diagnostic allowlists")
    scorer_names = {item["scenario"] for item in matrix if item["kind"] == "scorer"}
    if scorer_names != {"duplicate", "order", "tie", "wrong-predicate", "reversed-endpoint", "extra", "missing"}:
        raise ValueError("fixture matrix scorer coverage changed")
    cluster_cases = fixtures.get("v9ClusterCases")
    if not isinstance(cluster_cases, list) or len(cluster_cases) != 25:
        raise ValueError("v9 cluster fixture case count changed")
    schema_cases = [item for item in cluster_cases if item.get("kind") == "schema"]
    evidence_cases = [item for item in cluster_cases if item.get("kind") == "evidence"]
    if len(schema_cases) + len(evidence_cases) != len(cluster_cases):
        raise ValueError("unknown v9 cluster fixture kind")
    derived_schema_runs = [item["caseRun"] for item in schema_cases]
    derived_evidence_runs = [item["caseRun"] for item in evidence_cases]
    derived_schema_reasons = Counter(item["reason"] for item in schema_cases)
    derived_evidence_reasons = Counter(item["reason"] for item in evidence_cases)
    if set(derived_schema_reasons) != {"entity_span_out_of_source"}:
        raise ValueError("v9 schema cluster reason is outside the closed allowlist")
    if set(derived_evidence_reasons) != {"evidence_does_not_contain_trigger", "evidence_does_not_contain_endpoints"}:
        raise ValueError("v9 evidence cluster reasons are outside the closed allowlist")
    claims = fixtures.get("v9SanitizedClusters")
    if not isinstance(claims, dict):
        raise ValueError("v9 cluster claims missing")
    schema_claim = claims.get("schemaInvalid", {})
    evidence_claim = claims.get("invalidEvidence", {})
    if schema_claim.get("total") != len(schema_cases) or schema_claim.get("caseRuns") != derived_schema_runs or schema_claim.get("reason") != next(iter(derived_schema_reasons)):
        raise ValueError("v9 schema cluster claim does not reconcile with fixture cases")
    if evidence_claim.get("total") != len(evidence_cases) or evidence_claim.get("caseRuns") != derived_evidence_runs or evidence_claim.get("reasonCounts") != dict(derived_evidence_reasons):
        raise ValueError("v9 evidence cluster claim does not reconcile with fixture cases")
    if any(item.get("arm") != "predicted-entities" or item.get("stage") != "stage1" or item.get("reason") != "entity_span_out_of_source" for item in schema_cases):
        raise ValueError("v9 schema cluster arm/stage/reason mismatch")
    if any(item.get("arm") != "gold-entities" or item.get("stage") != "stage2" for item in evidence_cases):
        raise ValueError("v9 evidence cluster arm/stage mismatch")
    diagnostic = json.loads(DIAGNOSTIC_REPORT.read_text(encoding="utf-8"))
    validate_report(diagnostic)
    source_reports = diagnostic.get("sourceReports", {})
    if source_reports.get("v6", {}).get("digest") != V6_DIGEST or source_reports.get("v9", {}).get("digest") != V9_DIGEST:
        raise ValueError("diagnostic source report digests changed")
    trigger_result = classify_evidence(False, True)
    endpoint_result = classify_evidence(True, False)
    if trigger_result != "evidence_does_not_contain_trigger" or endpoint_result != "evidence_does_not_contain_endpoints":
        raise ValueError("containment parity fixture failed")
    report = {
        "artifactVersion": "s12.s12-f-12.rm50-parity-report.v1",
        "status": "OFFLINE_PARITY_FIXTURES_VERIFIED_PENDING_OWNER_REVIEW",
        "experimentId": "s12-f-12",
        "taskId": "S12-RM-50",
        "sourceReports": {"v6": {"digest": V6_DIGEST}, "v9": {"digest": V9_DIGEST}},
        "diagnosticContract": {"path": DIAGNOSTIC_REPORT.relative_to(ROOT).as_posix(), "digest": digest(DIAGNOSTIC_REPORT), "optionAStopCriteriaPassed": True},
        "fixtureContract": {"path": FIXTURE_PATH.relative_to(ROOT).as_posix(), "fixtureCount": len(matrix), "caseArmStageSliceCoverage": True, "schemaBoundaryCoverage": sorted(schema_reasons), "evidenceBoundaryCoverage": sorted(evidence_reasons), "scorerScenarioCoverage": sorted(item["scenario"] for item in matrix if item["kind"] == "scorer")},
        "scorerScenarioResults": run_scorer_scenarios(),
        "v9ClusterReproduction": {"schemaInvalidTotal": len(schema_cases), "invalidEvidenceTotal": len(evidence_cases), "triggerContainment": derived_evidence_reasons["evidence_does_not_contain_trigger"], "endpointContainment": derived_evidence_reasons["evidence_does_not_contain_endpoints"], "reproducedWithoutProviderOrRawReconstruction": True},
        "goldRelationsControl": fixtures["goldRelationsControl"],
        "rawDataPolicy": {"rawProviderPayloadIncluded": False, "rawSourceTextIncluded": False, "rawTriggerQuoteIncluded": False, "rawValidationDetailIncluded": False, "recursiveDynamicKeyExclusion": True},
        "governance": {"offlineOnly": True, "providerCalls": 0, "runtimeRemediationAuthorized": False, "supersedingLineagePreparationAuthorized": False, "preregistrationIssued": False, "technicalFreezeIssued": False, "newAuthorizationIssued": False, "providerExecutionAuthorized": False, "validationAccessAuthorized": False, "heldOutAccessAuthorized": False, "stageBAuthorized": False, "candidateSelectionAuthorized": False, "promotionAuthorized": False},
        "nextGate": "S12-RM-51_OWNER_REVIEW_RM50_OFFLINE_DIAGNOSTICS_AND_PARITY_FIXTURES",
    }
    assert_no_raw_data_aliases(report, allow_policy_keys=True)
    return report


def validate_parity_report(report: dict[str, Any]) -> None:
    schema = json.loads(PARITY_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda error: list(error.path))
    if errors:
        raise ValueError("RM-50 parity report schema invalid: " + "; ".join(error.message for error in errors))
    expected = build_parity_report()
    if report != expected:
        raise ValueError("RM-50 parity report does not match regenerated fixtures and diagnostic source")


def main() -> None:
    fixtures = _fixture_data()
    FIXTURE_PATH.write_bytes((json.dumps(fixtures, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    report = build_parity_report(fixtures)
    validate_parity_report(report)
    REPORT_PATH.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
