from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm50-parity-fixtures.v1.json"
FIXTURE_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-rm50-parity-fixtures.schema.v1.json"
REPORT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm50-parity-report.v1.json"
REPORT_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-rm50-parity-report.schema.v1.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm50-offline-remediation.v1.json"

import sys

sys.path.insert(0, str(ROOT / "scripts"))

from s12_f12_rm50_parity_fixtures import (  # noqa: E402
    build_parity_report,
    classify_evidence,
    digest,
    run_scorer_scenarios,
    validate_parity_report,
)


def test_option_b_fixture_and_report_schemas_are_closed() -> None:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    fixture_errors = list(Draft202012Validator(json.loads(FIXTURE_SCHEMA.read_text(encoding="utf-8"))).iter_errors(fixtures))
    report_errors = list(Draft202012Validator(json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))).iter_errors(report))
    assert not fixture_errors, [error.message for error in fixture_errors]
    assert not report_errors, [error.message for error in report_errors]
    assert build_parity_report(fixtures) == report


def test_option_b_covers_finite_boundaries_and_reproduces_v9_clusters() -> None:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    kinds = {item["kind"] for item in fixtures["fixtureMatrix"]}
    assert kinds == {"schema", "evidence", "scorer"}
    assert len([item for item in fixtures["fixtureMatrix"] if item["kind"] == "schema"]) == 9
    assert len([item for item in fixtures["fixtureMatrix"] if item["kind"] == "evidence"]) == 10
    assert len([item for item in fixtures["fixtureMatrix"] if item["kind"] == "scorer"]) == 7
    assert fixtures["v9SanitizedClusters"]["schemaInvalid"]["total"] == 5
    assert fixtures["v9SanitizedClusters"]["invalidEvidence"]["reasonCounts"] == {
        "evidence_does_not_contain_trigger": 14,
        "evidence_does_not_contain_endpoints": 6,
    }
    assert fixtures["goldRelationsControl"] == {"fixtureArm": "gold-relations", "invalidEvidence": 0, "integrityPass": True}


def test_option_b_trigger_and_endpoint_containment_are_finite() -> None:
    assert classify_evidence(False, True) == "evidence_does_not_contain_trigger"
    assert classify_evidence(True, False) == "evidence_does_not_contain_endpoints"
    assert classify_evidence(True, True) is None


def test_option_b_scorer_parity_covers_duplicate_order_tie_and_error_buckets() -> None:
    results = run_scorer_scenarios()
    assert set(results) == {"duplicate", "order", "tie", "wrong-predicate", "reversed-endpoint", "extra", "missing"}
    assert results["duplicate"]["exactMatch"] == 1 and results["duplicate"]["extraRelation"] == 1
    assert results["order"]["exactMatch"] == 2
    assert results["tie"]["tieOrderDeterministic"] is True
    assert results["wrong-predicate"]["wrongPredicate"] == 1
    assert results["reversed-endpoint"]["reversedEndpoint"] == 1
    assert results["extra"]["extraRelation"] == 1
    assert results["missing"]["missingRelation"] == 1
    assert all(result["goldReconciled"] and result["predictedReconciled"] for result in results.values())


def test_option_b_rejects_dynamic_raw_fixture_key() -> None:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    candidate = deepcopy(fixtures)
    candidate["v9SanitizedClusters"]["rawPayload"] = {"secret": True}
    with pytest.raises(ValueError):
        build_parity_report(candidate)


@pytest.mark.parametrize("mutation", ["total", "reasonCounts", "deleteCaseRun"])
def test_option_b_rejects_cluster_claim_or_case_run_mutations(mutation: str) -> None:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    candidate = deepcopy(fixtures)
    if mutation == "total":
        candidate["v9SanitizedClusters"]["invalidEvidence"]["total"] += 1
    elif mutation == "reasonCounts":
        candidate["v9SanitizedClusters"]["invalidEvidence"]["reasonCounts"]["evidence_does_not_contain_trigger"] += 1
    else:
        candidate["v9ClusterCases"].pop()
    with pytest.raises(ValueError):
        build_parity_report(candidate)


def test_option_b_rejects_direct_report_cluster_or_source_digest_mutations() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    candidate = deepcopy(report)
    candidate["v9ClusterReproduction"]["schemaInvalidTotal"] += 1
    with pytest.raises(ValueError, match="does not match"):
        validate_parity_report(candidate)
    candidate = deepcopy(report)
    candidate["sourceReports"]["v9"]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="does not match"):
        validate_parity_report(candidate)


def test_option_b_original_inputs_regenerate_byte_identically() -> None:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    report = build_parity_report(fixtures)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    assert rendered.encode("utf-8") == REPORT.read_bytes()


def test_option_b_package_binds_a_pass_and_preserves_historical_custody() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    assert package["authorization"]["optionAStopCriteriaPassed"] is True
    assert package["authorization"]["optionBExecuted"] is True
    assert package["governance"]["providerCalls"] == 0
    assert package["historicalCustody"]["v8ReportPresent"] is False
    for path, expected in package["boundDigests"].items():
        assert digest(ROOT / path) == expected, path
