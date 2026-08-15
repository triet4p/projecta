"""Offline contract tests for the blocked S12-f-07 execution package."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
API_SRC = ROOT / "apps/api/src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(API_SRC))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OPT = ROOT / "evaluation/sprint-12/optimization"
EVALUATOR = load_module("sprint12_evaluator", SCRIPTS / "sprint12_evaluator.py")
OPTIMIZATION = load_module("sprint12_optimization_f07", SCRIPTS / "sprint12_optimization.py")
STAGE_RUNNER = load_module(
    "run_sprint12_f07_prompt_experiment_test",
    SCRIPTS / "run_sprint12_f07_prompt_experiment.py",
)


def read_json(name: str) -> dict:
    return json.loads((OPT / name).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_prompt_v4_is_exactly_bound_and_runner_supports_it() -> None:
    from projecta_api.extraction.prompt import (
        PROMPT_V4_RELATION_DECISION_RUBRIC,
        prompt_variant_instructions,
    )

    artifact = OPT / "s12-f-07-prompt-v4-relation-decision-rubric.v1.txt"
    assert PROMPT_V4_RELATION_DECISION_RUBRIC.strip() == artifact.read_text(
        encoding="utf-8"
    ).strip()
    assert prompt_variant_instructions(
        "m3.prompt.v4.relation-decision-rubric"
    ) == PROMPT_V4_RELATION_DECISION_RUBRIC
    with pytest.raises(ValueError, match="unsupported prompt variant"):
        prompt_variant_instructions("m3.prompt.unknown")


def test_relation_instrumentation_is_sanitized_and_predicate_scoped() -> None:
    gold = [
        {
            "predicate": "implements",
            "sourceEntityId": "entity-01",
            "targetEntityId": "entity-02",
            "span": {"start": 10, "end": 20},
        }
    ]
    prediction = [
        {
            "predicate": "implements",
            "sourceEntityId": "entity-99",
            "targetEntityId": "entity-02",
            "span": {"startOffset": 10, "endOffset": 20},
        },
        {
            "predicate": "unsupported-predicate",
            "sourceEntityId": "entity-03",
            "targetEntityId": "entity-04",
            "span": {"startOffset": 30, "endOffset": 40},
        },
    ]
    result = EVALUATOR.score_extraction(
        {"entities": [], "relations": gold, "links": [], "abstention": {"required": False}},
        {"entities": [], "relations": prediction, "links": [], "abstention": {"required": False}},
        ["implements", "supports"],
    )
    instrumentation = result["relationInstrumentation"]
    assert instrumentation["version"] == "s12.relation-instrumentation.v1"
    assert instrumentation["countsByPredicate"]["implements"][
        "correctPredicateWrongEndpoint"
    ] == 1
    assert instrumentation["totals"]["unallowlistedPredictedPredicate"] == 1
    serialized = json.dumps(instrumentation, ensure_ascii=False)
    assert "entity-01" not in serialized
    assert "entity-99" not in serialized
    assert "rawText" not in serialized


def test_package_digests_registry_g5_v7_and_authorization_history_are_bound() -> None:
    prereg = read_json("s12-f-07-relation-prompt-preregistration.v2.json")
    registry = read_json("experiment-registry.v7.json")
    authorization = read_json("s12-f-07-authorization.v2.json")
    authorization_v1 = read_json("s12-f-07-authorization.v1.json")
    g5 = read_json("g5-packet.v7.json")
    prompt_artifact = OPT / prereg["promptArtifact"]["artifact"]
    implementation = ROOT / prereg["promptArtifact"]["implementation"]
    backlog = ROOT / prereg["sourceEvidence"]["errorBacklog"]

    assert prereg["status"] == "PREREGISTERED_NOT_EXECUTED"
    assert prereg["executionAuthorized"] is False
    assert prereg["promptArtifact"]["digest"] == digest(prompt_artifact)
    assert prereg["promptArtifact"]["implementationDigest"] == digest(implementation)
    assert prereg["sourceEvidence"]["errorBacklogDigest"] == digest(backlog)
    assert prereg["costAccounting"]["providerPriceConfigurationRequiredBeforeExecution"] is False
    assert prereg["costAccounting"]["providerPriceConfigurationRequiredBeforeSelection"] is True
    assert prereg["pricingContract"]["requiredBeforeExecution"] is False
    assert prereg["pricingContract"]["requiredBeforeSelection"] is True

    assert registry["registryVersion"] == "s12.experiment-registry.v7"
    OPTIMIZATION.validate_registry(registry)
    experiment = next(item for item in registry["experiments"] if item["experimentId"] == "s12-f-07")
    assert experiment["status"] == "REGISTERED"
    assert experiment["preregistration"]["digest"] == digest(OPT / "s12-f-07-relation-prompt-preregistration.v2.json")
    assert authorization["status"] == "APPROVED_FOR_DEVELOPMENT_STAGE_A"
    assert authorization["registry"]["digest"] == registry["registryDigest"]
    assert authorization["authorizationHistory"]["priorDigest"] == digest(
        OPT / "s12-f-07-authorization.v1.json"
    )
    assert authorization_v1["status"] == "PENDING_USER_AUTHORIZATION"
    assert g5["registryVersion"] == registry["registryVersion"]
    assert g5["pendingExperiment"]["authorizationDigest"] == digest(
        OPT / "s12-f-07-authorization.v2.json"
    )
    assert g5["pendingExperiment"]["executionAuthorized"] is True
    assert g5["candidateAvailable"] is False
    assert g5["selection"]["status"] == "NO_SELECTION"
    assert prereg["stageA"]["temporalPairing"] == {
        "strategy": "interleaved_paired_runs",
        "schedule": [
            {"pairId": "pair-1", "runNumber": 1, "armOrder": ["control", "candidate"]},
            {"pairId": "pair-2", "runNumber": 2, "armOrder": ["candidate", "control"]},
            {"pairId": "pair-3", "runNumber": 3, "armOrder": ["control", "candidate"]},
        ],
        "oneAttemptPerCase": True,
        "noRetryWithinEachRun": True,
    }


def test_case_selection_is_development_only_and_matches_manifest_profile() -> None:
    prereg = read_json("s12-f-07-relation-prompt-preregistration.v2.json")
    case_ids = tuple(prereg["stageA"]["caseIds"])
    assert len(case_ids) == 16
    assert len(set(case_ids)) == 16
    assert STAGE_RUNNER._case_profile(case_ids) == prereg["stageA"]["selectionProfile"]
    atomic = json.loads(
        (ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json").read_text(
            encoding="utf-8"
        )
    )
    by_id = {case["caseId"]: case for case in atomic["cases"]}
    assert all(by_id[case_id]["split"] == "development" for case_id in case_ids)


def test_control_and_candidate_change_only_prompt() -> None:
    prereg = read_json("s12-f-07-relation-prompt-preregistration.v2.json")
    control = prereg["control"]["configuration"]
    candidate = prereg["candidate"]["configuration"]
    candidate_without_prompt = dict(candidate)
    candidate_without_prompt["promptVersion"] = control["promptVersion"]
    assert candidate_without_prompt == control
    assert control["model"] == candidate["model"] == "deepseek-v4-flash"
    assert control["samplingConfiguration"] == candidate["samplingConfiguration"]
    assert prereg["changedDimension"] == "prompt"


def test_stage_b_and_candidate_gates_fail_closed_without_mislabelling_control() -> None:
    scored = {
        "case-1": {"status": "scored", "relationMacroF1": {"f1": 1.0}},
    }
    candidate = {
        "failureCounts": {},
        "missingOutputCount": 0,
        "perCase": scored,
    }
    failed_control = {
        "failureCounts": {"missing_output": 1},
        "missingOutputCount": 1,
        "perCase": {"case-1": {"status": "missing-output"}},
    }
    assert STAGE_RUNNER.arm_hard_gate([candidate]) is True
    assert STAGE_RUNNER.arm_hard_gate([failed_control]) is False
    assert read_json("g5-packet.v7.json")["pendingExperiment"]["stageBAuthorized"] is False
    assert STAGE_RUNNER.price_reports([candidate]) == "NOT_BOUND_PRESELECTION"


def test_execution_preflight_accepts_frozen_authorization_without_provider_call() -> None:
    prereg, case_ids = STAGE_RUNNER.preflight()
    assert prereg["executionAuthorized"] is False
    assert len(case_ids) == 16


def test_mocked_runner_executes_six_interleaved_invocations_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    prereg = read_json("s12-f-07-relation-prompt-preregistration.v2.json")
    case_ids = tuple(prereg["stageA"]["caseIds"])
    calls: list[dict] = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        missing = len(calls) == 2
        per_case = {}
        for case_id in kwargs["case_ids"]:
            if missing and case_id == kwargs["case_ids"][0]:
                per_case[case_id] = {"status": "missing-output"}
            else:
                per_case[case_id] = {
                    "status": "scored",
                    "entityMacroF1": {"f1": 1.0},
                    "relationMacroF1": {"f1": 1.0},
                    "abstentionAccuracy": 1.0,
                    "hallucinationRate": 0.0,
                    "linkMacroF1": {"f1": 1.0},
                }
        return {
            "status": "RUNTIME_BACKED_SCORED",
            "failureCount": 1 if missing else 0,
            "missingOutputCount": 1 if missing else 0,
            "operational": {
                "failureCounts": {"missing_output": 1} if missing else {},
                "usage": {"inputTokens": 10, "outputTokens": 5},
            },
            "metrics": {
                "entityMacroF1": {"f1": 1.0},
                "relationMacroF1": {"f1": 1.0},
                "abstentionAccuracy": 1.0,
                "hallucinationRate": 0.0,
                "linkMacroF1": {"f1": 1.0},
                "perCase": per_case,
            },
            "configuration": {"promptVersion": kwargs["prompt_variant"]},
            "digests": {},
        }

    variants, trace = STAGE_RUNNER.execute_stage_a(
        prereg, case_ids, runner=fake_runner, report_dir=tmp_path
    )
    assert [call["prompt_variant"] for call in calls] == [
        "m3.prompt.v3.supersession-guard",
        "m3.prompt.v4.relation-decision-rubric",
        "m3.prompt.v4.relation-decision-rubric",
        "m3.prompt.v3.supersession-guard",
        "m3.prompt.v3.supersession-guard",
        "m3.prompt.v4.relation-decision-rubric",
    ]
    assert len(calls) == 6
    assert all(tuple(call["case_ids"]) == case_ids for call in calls)
    assert [item["arm"] for item in trace] == [
        "control", "candidate", "candidate", "control", "control", "candidate"
    ]
    assert len(list(tmp_path.glob("*.report.v1.json"))) == 6
    assert STAGE_RUNNER.arm_hard_gate(variants["candidate"]) is False
    with pytest.raises(SystemExit, match="refusing to overwrite run report"):
        STAGE_RUNNER.execute_stage_a(
            prereg, case_ids, runner=fake_runner, report_dir=tmp_path
        )
