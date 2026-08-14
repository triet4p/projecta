"""Contract checks for the Sprint 12 Phase C/G2 pilot packet."""

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/sprint-plans/sprint-12.md"
PACKET = ROOT / "docs/sprint-plans/sprint-12/g2-annotation-pilot.md"
PILOT = ROOT / "evaluation/sprint-12/pilot"
SCHEMA = ROOT / "evaluation/sprint-12/schema/scenario-case.schema.json"
ARTIFACTS = ROOT / "docs/sprint-plans/sprint-12/artifacts"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _span_set(label_set: dict) -> set[tuple[str, str]]:
    return {
        (case["caseId"], signature)
        for case in label_set["cases"]
        for signature in case["spanSignatures"]
    }


def _relation_link_set(label_set: dict) -> set[tuple[str, str]]:
    return {
        (case["caseId"], value)
        for case in label_set["cases"]
        for value in case["relationPredicates"] + case["linkTargets"]
    }


def _f1(left: set, right: set) -> float:
    intersection = len(left & right)
    return 2 * intersection / (len(left) + len(right))


def test_phase_c_tasks_and_g2_approval_boundary_are_recorded() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    assert "Status: `G3_APPROVED_G4_PENDING`" in plan
    assert "**Status:** `G2_APPROVED_G3_PENDING`" in PACKET.read_text(encoding="utf-8")
    assert "[x] **S12-29" in plan
    assert "[x] **S12-30" in plan
    assert "[x] **S12-31" in plan
    for number in range(32, 38):
        assert f"[ ] **S12-{number:02d}" in plan
    assert "[x] **S12-38 — Prepare the draft G2 packet" in plan
    assert "[x] **S12-39" in plan


def test_pilot_has_twenty_cases_three_scenarios_and_real_digests() -> None:
    atomic = _read_json(PILOT / "atomic-pilot.v1.json")
    scenarios = _read_json(PILOT / "scenario-pilot.v1.json")
    schema = _read_json(SCHEMA)
    assert atomic["status"] == "AGENT_GENERATED_CALIBRATION_FIXTURE"
    assert len(atomic["cases"]) == 20
    case_ids = {case["caseId"] for case in atomic["cases"]}
    assert len(case_ids) == 20
    assert {case["source"]["language"] for case in atomic["cases"]} == {"vi", "en", "ja", "mixed"}
    for case in atomic["cases"]:
        source = case["source"]
        digest = hashlib.sha256(source["rawText"].encode("utf-8")).hexdigest()
        assert source["contentDigest"] == f"sha256:{digest}"
        for item in case["gold"]["entities"] + case["gold"]["relations"] + case["gold"]["links"]:
            span = item["span"]
            assert source["rawText"][span["start"] : span["end"]] == span["text"]
            assert span["start"] < span["end"]

    required = set(schema["required"])
    assert len(scenarios["scenarios"]) == 3
    for scenario in scenarios["scenarios"]:
        assert required <= scenario.keys()
        assert set(scenario) <= set(schema["properties"])
        assert len(scenario["events"]) == 5
        event_case_ids = [event["caseId"] for event in scenario["events"]]
        assert scenario["sourceManifest"] == event_case_ids
        assert set(event_case_ids) <= case_ids
        for event in scenario["events"]:
            assert {"eventId", "sequence", "caseId", "expectedReview"} <= event.keys()
            assert {"disposition", "correctionClass"} <= event["expectedReview"].keys()
        for checkpoint in scenario["checkpoints"]:
            assert {"afterSequence", "sourceIds", "candidateIds", "assertedIds", "inferredExpectations", "provenanceActivityIds"} <= checkpoint.keys()
        for answer in scenario["competencyAnswers"]:
            assert {"questionId", "status", "expectedFactIds", "expectedCitationIds", "completeness", "freshness", "abstain"} <= answer.keys()


def test_fixture_labels_and_agreement_report_are_recomputed_and_nonhuman() -> None:
    label_a = _read_json(PILOT / "labels/annotator-a.v1.json")
    label_b = _read_json(PILOT / "labels/annotator-b.v1.json")
    report = _read_json(PILOT / "agreement-report.v1.json")
    assert len(label_a["cases"]) == len(label_b["cases"]) == 20
    assert label_a["humanEvidence"] is False
    assert label_b["humanEvidence"] is False
    assert report["humanEvidence"] is False

    spans_a = _span_set(label_a)
    spans_b = _span_set(label_b)
    assert len(spans_a) == 18
    assert len(spans_b) == 19
    assert len(spans_a & spans_b) == 18
    assert math.isclose(report["spanF1"], _f1(spans_a, spans_b))
    assert report["spanCounts"] == {"annotatorA": 18, "annotatorB": 19, "intersection": 18, "microF1Numerator": 36, "microF1Denominator": 37}

    by_id_b = {case["caseId"]: case for case in label_b["cases"]}
    exact_case_agreement = sum(
        case == by_id_b[case["caseId"]] for case in label_a["cases"]
    ) / len(label_a["cases"])
    assert math.isclose(report["exactCaseAgreement"], exact_case_agreement)
    type_abstention_agreement = sum(
        (case["entityTypes"], case["abstention"])
        == (by_id_b[case["caseId"]]["entityTypes"], by_id_b[case["caseId"]]["abstention"])
        for case in label_a["cases"]
    ) / len(label_a["cases"])
    assert math.isclose(report["typeAndAbstentionAgreement"], type_abstention_agreement)

    relation_links_a = _relation_link_set(label_a)
    relation_links_b = _relation_link_set(label_b)
    assert math.isclose(report["relationLinkF1"], _f1(relation_links_a, relation_links_b))
    assert report["scenarioGraphStateAgreement"] is None
    assert report["scenarioGraphStateStatus"] == "not_evaluated_missing_independent_scenario_labels"
    assert report["questionAnswerAgreement"] is None
    assert report["questionAnswerStatus"] == "not_evaluated_missing_independent_question_labels"
    assert report["fixturePassesProvisionalThresholds"] is False
    assert report["recomputedFromInputs"] is True

    adjudication = _read_json(PILOT / "adjudication-log.v1.json")
    assert adjudication["unresolvedDisagreements"] == 0
    assert next(item for item in adjudication["disagreements"] if item["caseId"] == "s12-a-0009")["accepted"] == "abstain"


def test_guide_and_gold_apply_research_context_rule() -> None:
    atomic = _read_json(PILOT / "atomic-pilot.v1.json")
    case = next(case for case in atomic["cases"] if case["caseId"] == "s12-a-0009")
    assert case["gold"]["entities"] == []
    assert case["gold"]["abstention"]["required"] is True
    guide = (PILOT / "annotation-guide.v1.1.md").read_text(encoding="utf-8")
    assert "If the context cannot" in guide
    assert "resolve the distinction" in guide


def test_g2_packet_records_approval_with_explicit_limitations() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    for section in [
        "Pilot package",
        "Fixture validation and provisional results",
        "Known preparation blockers",
        "Human evidence required for G2",
        "G2 acceptance checklist",
        "Approval record (S12-39)",
    ]:
        assert section in packet
    assert "**Status:** `G2_APPROVED_G3_PENDING`" in packet
    assert "| G2 outcome | `APPROVED_WITH_LIMITATIONS` |" in packet
    assert "0.97297" in packet
    assert "No independent scenario labels supplied" in packet
    assert "- [ ] Qualified human annotation evidence is supplied." in packet
    assert "- [x] Project owner approves G2 annotation reliability with the limitations" in packet
    assert "These limitations are accepted as explicit residual risks" in packet


def test_phase_c_summaries_and_guide_revision_exist() -> None:
    for number in range(29, 40):
        summary = ARTIFACTS / f"task_S12-{number:02d}_summary.md"
        assert summary.exists(), summary
        content = summary.read_text(encoding="utf-8")
        assert f"S12-{number:02d}" in content
        assert "## Testing" in content
    guide = (PILOT / "annotation-guide.v1.1.md").read_text(encoding="utf-8")
    assert "AG-01" in guide
    assert "AG-02" in guide
