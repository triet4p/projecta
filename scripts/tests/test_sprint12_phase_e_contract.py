"""Contract and adversarial self-tests for the Sprint 12 Phase E evaluator."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_evaluator", ROOT / "scripts/sprint12_evaluator.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def paths() -> tuple[Path, Path, Path]:
    corpus = ROOT / "evaluation/sprint-12/corpus"
    return (
        corpus / "atomic-development-validation.v1.json",
        corpus / "scenario-development-validation.v1.json",
        corpus / "manifests/development-validation.manifest.v1.json",
    )


def test_phase_e_loader_accepts_bound_development_validation_fixture() -> None:
    loaded = MODULE.load_dataset(*paths())
    assert len(loaded.cases) == 160
    assert len(loaded.scenarios) == 18
    assert loaded.manifest["manifestVersion"] == "s12.corpus.manifest.v1"


def test_loader_rejects_unknown_schema_and_tampered_source(tmp_path: Path) -> None:
    atomic_path, scenario_path, manifest_path = paths()
    atomic = read_json(atomic_path)
    atomic["cases"][0]["schemaVersion"] = "s12.atomic.unknown"
    broken_atomic = tmp_path / "atomic.json"
    broken_atomic.write_text(json.dumps(atomic), encoding="utf-8")
    with pytest.raises(MODULE.EvaluationError, match="unknown schema"):
        MODULE.load_dataset(broken_atomic, scenario_path, manifest_path)

    atomic = read_json(atomic_path)
    atomic["cases"][0]["source"]["rawText"] += " tampered"
    broken_atomic.write_text(json.dumps(atomic), encoding="utf-8")
    with pytest.raises(MODULE.EvaluationError, match="tampered source digest"):
        MODULE.load_dataset(broken_atomic, scenario_path, manifest_path)


def test_loader_rejects_split_policy_and_cross_file_reference(tmp_path: Path) -> None:
    atomic_path, scenario_path, manifest_path = paths()
    atomic = read_json(atomic_path)
    atomic["cases"][0]["split"] = "test"
    broken_atomic = tmp_path / "atomic.json"
    broken_atomic.write_text(json.dumps(atomic), encoding="utf-8")
    with pytest.raises(MODULE.EvaluationError, match="test split is sealed"):
        MODULE.load_dataset(broken_atomic, scenario_path, manifest_path)

    scenario = read_json(scenario_path)
    scenario["scenarios"][0]["sourceManifest"].append("s12-a-9999")
    broken_scenario = tmp_path / "scenario.json"
    broken_scenario.write_text(json.dumps(scenario), encoding="utf-8")
    with pytest.raises(MODULE.EvaluationError, match="invalid scenario references"):
        MODULE.load_dataset(atomic_path, broken_scenario, manifest_path)


def test_integrity_rejects_duplicate_manifest_ids_and_digest_leakage() -> None:
    manifest = read_json(paths()[2])
    duplicate = copy.deepcopy(manifest)
    duplicate["atomicCases"].append(copy.deepcopy(duplicate["atomicCases"][0]))
    with pytest.raises(MODULE.EvaluationError, match="duplicate manifest ID"):
        MODULE._validate_manifest(duplicate)

    leakage = copy.deepcopy(manifest)
    leakage["atomicCases"][1]["contentDigest"] = leakage["atomicCases"][0][
        "contentDigest"
    ]
    with pytest.raises(MODULE.EvaluationError, match="duplicate content digest"):
        MODULE._validate_manifest(leakage)


def test_metrics_fail_explicitly_on_missing_output_and_handle_empty_sets() -> None:
    gold = {
        "entities": [],
        "relations": [],
        "links": [],
        "abstention": {"required": True},
        "semanticGaps": [],
    }
    assert MODULE.score_extraction(gold, None)["status"] == "missing-output"
    scored = MODULE.score_extraction(
        gold,
        {
            "entities": [],
            "relations": [],
            "links": [],
            "abstention": {"required": True},
        },
    )
    assert scored["status"] == "scored"
    assert scored["entities"]["f1"] == 1.0
    assert MODULE.calibration([], []) == {"status": "not-available"}
    assert MODULE.score_ontology_mapping({}, None)["status"] == "missing-output"
    assert MODULE.score_scenario({}, None)["status"] == "missing-output"
    assert MODULE.score_retrieval({}, None)["status"] == "missing-output"


def test_report_is_digest_bound_and_contains_no_source_text() -> None:
    loaded = MODULE.load_dataset(*paths())
    report = MODULE.build_evidence_report(loaded, config={"release": "v0.6.0"})
    raw_text = loaded.cases[0]["source"]["rawText"]
    assert report["manifestDigest"] == loaded.manifest["manifestDigest"]
    assert report["configurationDigest"].startswith("sha256:")
    assert report["omittedCaseCount"] == 0
    assert report["rawSensitiveDataIncluded"] is False
    assert raw_text not in json.dumps(report, ensure_ascii=False)


def test_reviewer_utility_rejects_raw_sensitive_fields() -> None:
    with pytest.raises(MODULE.EvaluationError, match="raw sensitive data"):
        MODULE.score_reviewer_utility(
            [{"disposition": "confirmed", "sourceText": "secret"}]
        )
    result = MODULE.score_reviewer_utility(
        [
            {
                "disposition": "confirmed",
                "correctionClass": "unchanged",
                "usefulness": 4,
                "trust": 5,
            }
        ]
    )
    assert result["count"] == 1
    assert result["usefulness"] == 4.0


def test_baseline_stops_without_runtime_configuration() -> None:
    loaded = MODULE.load_dataset(*paths())
    report = MODULE.build_baseline_report(loaded, environment={})
    assert report["status"] == "NOT_EXECUTED_MISSING_RUNTIME_CONFIGURATION"
    assert report["missingOutputCount"] == 160
    assert report["errorTaxonomy"]["observations"][0]["category"] == "runtime"


def test_g4_approval_records_limitation_without_unlocking_optimization() -> None:
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    packet = (ROOT / "docs/sprint-plans/sprint-12/g4-baseline.md").read_text(
        encoding="utf-8"
    )
    assert "Status: `G4_APPROVED_WITH_LIMITATIONS_G5_PENDING`" in plan
    assert "[x] **S12-71" in plan
    assert "`APPROVED_WITH_LIMITATIONS`" in packet
    assert "No optimization or held-out evaluation unlock" in packet


def test_error_taxonomy_is_finite() -> None:
    assert MODULE.classify_error({"category": "ontology"}) == "ontology"
    with pytest.raises(MODULE.EvaluationError, match="unknown baseline error category"):
        MODULE.classify_error({"category": "mystery"})
