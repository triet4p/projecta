"""Offline contracts for the rejected S12-f-07 closure and S12-f-08 preregistration."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
OPT = ROOT / "evaluation/sprint-12/optimization"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps/api/src"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EVALUATOR = load_module("sprint12_evaluator", ROOT / "scripts/sprint12_evaluator.py")
OPTIMIZATION = load_module("sprint12_optimization_f08", ROOT / "scripts/sprint12_optimization.py")
RUNNER = load_module(
    "run_sprint12_f07_prompt_experiment_f08_test",
    ROOT / "scripts/run_sprint12_f07_prompt_experiment.py",
)


def read_json(name: str) -> dict:
    return json.loads((OPT / name).read_text(encoding="utf-8"))


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_f07_erratum_corrects_mapping_without_rewriting_aggregate() -> None:
    aggregate_path = OPT / "s12-f-07-relation-prompt-stage-a.v1.json"
    erratum = read_json("s12-f-07-scoring-erratum.v1.json")
    aggregate = read_json(aggregate_path.name)
    assert erratum["immutableEvidence"] is True
    assert erratum["sourceAggregate"]["digest"] == file_digest(aggregate_path)
    assert erratum["correctedMetrics"]["control"]["entityMacroF1"] == 0.75
    assert erratum["correctedMetrics"]["candidate"]["entityMacroF1"] == pytest.approx(0.5416666667)
    assert erratum["correctedMetrics"]["delta"]["entityMacroF1"] == pytest.approx(-0.2083333333)
    assert erratum["correctedMetrics"]["control"]["positiveRelationCaseRuns"] == 21
    assert erratum["correctedMetrics"]["candidate"]["positiveRelationMacroF1"] == 0.0
    assert erratum["relationMetricStatus"] == "PROVISIONAL_MEASUREMENT_LIMITATION"
    assert erratum["hardGates"]["decisionPreserved"] is True
    assert aggregate["decision"] == "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"


def test_f07_case_metric_maps_to_persisted_entity_and_relation_fields() -> None:
    scored = {
        "status": "scored",
        "entities": {"f1": 0.75},
        "relations": {"f1": 0.50, "gold": 1, "predicted": 1, "truePositive": 0},
    }
    assert RUNNER._case_metric(scored, "entityMacroF1") == 0.75
    assert RUNNER._case_metric(scored, "relationMacroF1") == 0.50
    metrics = RUNNER.primary_metrics(
        [{"perCase": {"positive": scored, "empty": {"status": "scored", "entities": {"f1": 1.0}, "relations": {"f1": 1.0, "gold": 0, "predicted": 0, "truePositive": 0}}}}]
    )
    assert metrics["positiveRelationMacroF1"] == 0.50
    assert metrics["positiveRelationMicroF1"] == 0.0


def test_relation_scoring_uses_canonical_entity_spans_and_separates_reversal() -> None:
    gold = {
        "entities": [
            {"id": "entity-01", "type": "Task", "span": {"start": 0, "end": 4}},
            {"id": "entity-02", "type": "Requirement", "span": {"start": 10, "end": 20}},
        ],
        "relations": [{"predicate": "implements", "sourceEntityId": "entity-01", "targetEntityId": "entity-02", "span": {"start": 0, "end": 20}}],
        "links": [],
        "abstention": {"required": False},
    }
    prediction = {
        "entities": [
            {"candidateId": "candidate-a", "type": "Task", "span": {"startOffset": 0, "endOffset": 4}},
            {"candidateId": "candidate-b", "type": "Requirement", "span": {"startOffset": 10, "endOffset": 20}},
        ],
        "relations": [{"predicate": "implements", "sourceEntityId": "candidate-b", "targetEntityId": "candidate-a", "span": {"startOffset": 0, "endOffset": 20}}],
        "links": [],
        "abstention": {"required": False},
    }
    result = EVALUATOR.score_extraction(gold, prediction, ["implements"])
    assert result["relations"]["f1"] == 0.0
    assert result["relationInstrumentation"]["totals"]["reversedEndpoint"] == 1
    serialized = json.dumps(result["relationInstrumentation"])
    assert "entity-01" not in serialized
    assert "candidate-a" not in serialized


def test_prompt_v5_is_composed_and_f08_is_locked_before_execution() -> None:
    from projecta_api.extraction.prompt import (
        PROMPT_V3_SUPERSESSION_GUARD,
        PROMPT_V4_RELATION_DECISION_RUBRIC,
        PROMPT_V5_COMPOSED_RELATION_CONTRACT,
        build_extraction_prompt,
        prompt_variant_instructions,
    )

    artifact = OPT / "s12-f-08-prompt-v5-composed-relation-contract.v1.txt"
    assert PROMPT_V5_COMPOSED_RELATION_CONTRACT.strip() == artifact.read_text(encoding="utf-8").strip()
    assert PROMPT_V3_SUPERSESSION_GUARD in PROMPT_V5_COMPOSED_RELATION_CONTRACT
    assert PROMPT_V4_RELATION_DECISION_RUBRIC in PROMPT_V5_COMPOSED_RELATION_CONTRACT
    assert prompt_variant_instructions("m3.prompt.v5.composed-relation-contract") == PROMPT_V5_COMPOSED_RELATION_CONTRACT
    system_prompt, _ = build_extraction_prompt(
        'The address validation task implements the checkout requirement.',
        ["Task", "Requirement"],
        ["implements"],
        [],
        schema_version="m3.v2",
    )
    assert "two typed entity candidates" in system_prompt
    assert "sourceEntityId" in system_prompt and "targetEntityId" in system_prompt

    prereg = read_json("s12-f-08-relation-prompt-preregistration.v1.json")
    auth = read_json("s12-f-08-authorization.v1.json")
    assert prereg["status"] == "PREREGISTERED_NOT_EXECUTED"
    assert prereg["executionAuthorized"] is False
    assert prereg["candidate"]["configuration"]["promptVersion"] == "m3.prompt.v5.composed-relation-contract"
    assert prereg["pricingContract"]["requiredBeforeExecution"] is True
    assert auth["status"] == "PENDING_USER_AUTHORIZATION"
    assert len(prereg["stageA"]["caseIds"]) == 16
    assert RUNNER._case_profile(tuple(prereg["stageA"]["caseIds"])) == prereg["stageA"]["selectionProfile"]


def test_registry_v8_closes_f07_and_opens_f08_without_selection() -> None:
    registry = read_json("experiment-registry.v8.json")
    g5 = read_json("g5-packet.v8.json")
    OPTIMIZATION.validate_registry(registry)
    f07 = next(item for item in registry["experiments"] if item["experimentId"] == "s12-f-07")
    f08 = next(item for item in registry["experiments"] if item["experimentId"] == "s12-f-08")
    assert registry["registryVersion"] == "s12.experiment-registry.v8"
    assert f07["status"] == "COMPLETED_REJECTED"
    assert f07["executionEvidence"]["decision"] == "REJECTED_NO_STAGE_B_NO_SELECTION"
    assert f08["status"] == "REGISTERED_PENDING_AUTHORIZATION"
    assert g5["closedExperiment"]["noStageB"] is True
    assert g5["closedExperiment"]["noCandidateSelection"] is True
    assert g5["pendingExperiment"]["executionAuthorized"] is False
    assert g5["selection"]["status"] == "NO_SELECTION"
