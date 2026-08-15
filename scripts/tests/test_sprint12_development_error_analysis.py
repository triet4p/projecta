import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "evaluation" / "sprint-12" / "optimization" / "development-error-analysis.v1.json"


def test_development_backlog_is_fully_accounted_and_development_only():
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    accounting = data["outputAccounting"]

    assert data["providerCallsMade"] is False
    assert data["heldOutInspected"] is False
    assert data["split"] == "development"
    assert accounting["accountingComplete"] is True
    assert accounting["expectedCaseRunCount"] == accounting["accountedCaseRunCount"]
    assert accounting["missingOutputsFailExplicit"] is True
    assert all(item["split"] == "development" for item in data["caseRuns"])
    assert all(item["accounting"]["caseCoveragePresent"] for item in data["caseRuns"])


def test_relation_hypothesis_is_approved_but_stage_a_is_not_executed():
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    decision = data["hypothesisDecision"]
    experiment = data["recommendedNextExperiment"]

    assert decision["decision"] == "APPROVE_ONE_RELATION_FOCUSED_PROMPT_HYPOTHESIS"
    assert decision["relationPositiveCaseRunCount"] > 0
    assert decision["relationErrorCaseRunCount"] > 0
    assert experiment["status"] == "PREREGISTERED_NOT_EXECUTED"
    assert experiment["model"] == "deepseek-v4-flash"
    assert experiment["candidatePrompt"] == "m3.prompt.v4.relation-decision-rubric"
    assert experiment["stageA"]["caseCount"] == 16
    assert experiment["stageA"]["independentPairedRuns"] == 3
    assert "deepseek-v4-pro" in experiment["doNotRun"]
