"""Contract and adversarial self-tests for the Sprint 12 Phase E evaluator."""

import copy
import importlib.util
import json
import sys
from dataclasses import replace
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


def adjudicated_v2_paths() -> tuple[Path, Path, Path]:
    corpus = ROOT / "evaluation/sprint-12/corpus"
    return (
        corpus / "atomic-development-validation.v2.json",
        corpus / "scenario-development-validation.v2.json",
        corpus / "manifests/development-validation.manifest.v2.json",
    )


def test_phase_e_loader_accepts_bound_development_validation_fixture() -> None:
    loaded = MODULE.load_dataset(*paths())
    assert len(loaded.cases) == 160
    assert len(loaded.scenarios) == 18
    assert loaded.manifest["manifestVersion"] == "s12.corpus.manifest.v1"


def test_supersession_adjudication_is_a_new_dataset_version_and_v1_is_unchanged() -> None:
    original = MODULE.load_dataset(*paths())
    amended = MODULE.load_dataset(*adjudicated_v2_paths())
    original_case = next(case for case in original.cases if case["caseId"] == "s12-a-0106")
    amended_case = next(case for case in amended.cases if case["caseId"] == "s12-a-0106")
    assert original.dataset["datasetVersion"] == "s12.corpus.atomic.v1"
    assert amended.dataset["datasetVersion"] == "s12.corpus.atomic.v2"
    assert original.manifest["manifestVersion"] == "s12.corpus.manifest.v1"
    assert amended.manifest["manifestVersion"] == "s12.corpus.manifest.v2"
    assert original_case["gold"]["entities"]
    assert amended_case["gold"] == {
        "entities": [],
        "relations": [],
        "links": [],
        "abstention": {
            "required": True,
            "reason": "supersession clause is not an independently supported Requirement; the supersedes predicate is outside the current candidate allowlist",
        },
        "semanticGaps": [
            {
                "label": "candidate-contract-supersedes",
                "rationale": "The released ontology supports supersession, but the atomic candidate relation allowlist does not expose it; lifecycle scoring remains scenario-level.",
                "candidateReleasedTerm": "supersedes",
            }
        ],
    }
    adjudication = read_json(
        ROOT / "evaluation/sprint-12/baseline/supersession-adjudication.v2.json"
    )
    assert adjudication["goldChangedSilently"] is False
    assert adjudication["changedCaseCount"] == 21


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


def test_span_scoring_canonicalizes_gold_and_v2_prediction_offsets() -> None:
    gold = {
        "entities": [
            {"type": "Task", "span": {"start": 17, "end": 34, "text": "task"}}
        ],
        "relations": [
            {
                "predicate": "implements",
                "sourceEntityId": "entity-01",
                "targetEntityId": "entity-02",
                "span": {"start": 17, "end": 34, "text": "relation"},
            }
        ],
        "links": [],
        "abstention": {"required": False},
    }
    prediction = {
        "entities": [
            {
                "type": "Task",
                "span": {"startOffset": 17, "endOffset": 34, "text": "task"},
            }
        ],
        "relations": [
            {
                "predicate": "implements",
                "sourceEntityId": "entity-01",
                "targetEntityId": "entity-02",
                "span": {
                    "startOffset": 17,
                    "endOffset": 34,
                    "text": "relation",
                },
            }
        ],
        "links": [],
        "abstention": {"required": False},
    }
    result = MODULE.score_extraction(gold, prediction)
    assert result["entities"]["f1"] == 1.0
    assert result["relations"]["f1"] == 1.0


def test_span_scoring_rejects_off_by_one_and_wrong_entity_type() -> None:
    gold = {
        "entities": [{"type": "Task", "span": {"start": 17, "end": 34}}],
        "relations": [],
        "links": [],
        "abstention": {"required": False},
    }
    off_by_one = {
        "entities": [
            {"type": "Task", "span": {"startOffset": 17, "endOffset": 35}}
        ],
        "relations": [],
        "links": [],
        "abstention": {"required": False},
    }
    wrong_type = {
        "entities": [
            {"type": "Requirement", "span": {"startOffset": 17, "endOffset": 34}}
        ],
        "relations": [],
        "links": [],
        "abstention": {"required": False},
    }
    assert MODULE.score_extraction(gold, off_by_one)["entities"]["f1"] == 0.0
    assert MODULE.score_extraction(gold, wrong_type)["entities"]["f1"] == 0.0


def test_relation_scoring_rejects_wrong_predicate_and_missing_output() -> None:
    gold = {
        "entities": [],
        "relations": [
            {
                "predicate": "implements",
                "sourceEntityId": "entity-01",
                "targetEntityId": "entity-02",
                "span": {"start": 1, "end": 5},
            }
        ],
        "links": [],
        "abstention": {"required": False},
    }
    wrong_predicate = {
        "entities": [],
        "relations": [
            {
                "predicate": "supports",
                "sourceEntityId": "entity-01",
                "targetEntityId": "entity-02",
                "span": {"startOffset": 1, "endOffset": 5},
            }
        ],
        "links": [],
        "abstention": {"required": False},
    }
    assert MODULE.score_extraction(gold, wrong_predicate)["relations"]["f1"] == 0.0
    assert MODULE.score_extraction(gold, None)["status"] == "missing-output"


def test_report_is_digest_bound_and_contains_no_source_text() -> None:
    loaded = MODULE.load_dataset(*paths())
    report = MODULE.build_evidence_report(loaded, config={"release": "v0.6.0"})
    raw_text = loaded.cases[0]["source"]["rawText"]
    assert report["manifestDigest"] == loaded.manifest["manifestDigest"]
    assert report["configurationDigest"].startswith("sha256:")
    assert report["omittedCaseCount"] == 0
    assert report["rawSensitiveDataIncluded"] is False
    assert raw_text not in json.dumps(report, ensure_ascii=False)


def test_baseline_scoring_erratum_preserves_historical_execution_evidence() -> None:
    lock = read_json(ROOT / "evaluation/sprint-12/baseline/baseline-lock.v1.json")
    erratum = read_json(
        ROOT / "evaluation/sprint-12/baseline/baseline-scoring-erratum.v1.json"
    )
    assert erratum["baselineReportDigest"] == lock["reportDigest"]
    assert erratum["executionEvidence"]["caseCount"] == 160
    assert erratum["executionEvidence"]["failureCount"] == 55
    assert erratum["scoringDefect"]["historicalMetricsReliable"] is False
    assert erratum["scoringDefect"]["executionEvidenceReliable"] is True
    assert erratum["correctiveAction"]["historicalReportOverwritten"] is False


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


def test_runtime_adapter_runs_one_bounded_attempt_per_case_without_network() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from projecta_api.extraction.contracts import ExtractionResponse, UsageMetadata
    from projecta_api.llm.gateway import GatewayResponse

    class FakeGateway:
        async def extract(self, request: object) -> GatewayResponse:
            del request
            return GatewayResponse(
                extraction=ExtractionResponse(
                    schemaVersion="m3.v1",
                    modelId="fixture-model",
                    modelVersion="fixture-model",
                    abstentionReason="bounded runtime probe",
                    usage=UsageMetadata(inputTokens=3, outputTokens=2, totalTokens=5),
                )
            )

    loaded = MODULE.load_dataset(*paths())
    environment = {
        "PROJECTA_LLM_TYPE": "openai-response",
        "PROJECTA_LLM_BASE_URL": "https://fixture.invalid",
        "PROJECTA_LLM_API_KEY": "fixture-key",
        "PROJECTA_LLM_MODEL": "fixture-model",
    }
    case_results, operational, failures, config = MODULE._runtime_baseline(
        loaded, environment, gateway_factory=lambda _base_url, _api_key: FakeGateway()
    )
    assert len(case_results) == 160
    assert len(operational) == 160
    assert failures == []
    assert config["oneAttemptPerCase"] is True


def test_runtime_adapter_can_run_opt_in_m3_v2_contract_without_changing_v1() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from projecta_api.extraction.contracts import ExtractionResponse
    from projecta_api.llm.gateway import GatewayResponse

    requests: list[object] = []

    class FakeGateway:
        async def extract(self, request: object) -> GatewayResponse:
            requests.append(request)
            return GatewayResponse(
                extraction=ExtractionResponse(
                    schemaVersion="m3.v2",
                    modelId="fixture-model",
                    modelVersion="fixture-model",
                    abstentionReason="bounded v2 probe",
                )
            )

    loaded = MODULE.load_dataset(*paths())
    loaded = replace(loaded, cases=loaded.cases[:1])
    environment = {
        "PROJECTA_LLM_TYPE": "openai-response",
        "PROJECTA_LLM_BASE_URL": "https://fixture.invalid",
        "PROJECTA_LLM_API_KEY": "fixture-key",
        "PROJECTA_LLM_MODEL": "fixture-model",
    }
    _, _, failures, config = MODULE._runtime_baseline(
        loaded,
        environment,
        gateway_factory=lambda _base_url, _api_key: FakeGateway(),
        schema_version="m3.v2",
        operation_id="s12-g4.1-v2-probe",
        profile_revision="contract-v2-probe",
    )

    assert failures == []
    assert config["schemaVersion"] == "m3.v2"
    assert requests[0].schema_version == "m3.v2"  # type: ignore[attr-defined]
    assert requests[0].source_text is not None  # type: ignore[attr-defined]


def test_g4_approval_records_limitation_without_unlocking_optimization() -> None:
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    packet = (ROOT / "docs/sprint-plans/sprint-12/g4-baseline.md").read_text(
        encoding="utf-8"
    )
    assert "Status: `G6_PREPARATION_BLOCKED_CUSTODY_OR_CANDIDATE`" in plan
    assert "[x] **S12-71" in plan
    assert "`APPROVED_WITH_LIMITATIONS`" in packet
    assert "No optimization or held-out evaluation unlock" in packet


def test_error_taxonomy_is_finite() -> None:
    assert MODULE.classify_error({"category": "ontology"}) == "ontology"
    with pytest.raises(MODULE.EvaluationError, match="unknown baseline error category"):
        MODULE.classify_error({"category": "mystery"})
