#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate the lineage-disjoint S12 v3 scale track from approved pilot patterns."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/corpus/v3-scale"
PREDICATES = ("implements", "blocks", "dependsOn", "supports", "answers", "constrainedBy")
LANGUAGE_A = ("vi", "en", "mixed", "vi", "ja", "en", "vi", "mixed")
LANGUAGE_B = ("vi", "vi", "mixed", "vi", "ja", "en", "vi", "mixed")
DOMAINS = (
    ("cargo-routing", "Dock 7", "dispatch board", "routing window"),
    ("vendor-invoice", "AP lead", "invoice queue", "tax receipt"),
    ("roster-planning", "shift lead", "roster board", "coverage gap"),
    ("mobile-wallet", "Treasury", "settlement job", "refund window"),
    ("lab-sample", "lab coordinator", "sample queue", "barcode mismatch"),
    ("fleet-inspection", "fleet lead", "inspection form", "service hold"),
    ("member-renewal", "Membership", "renewal flow", "expired consent"),
    ("course-enrolment", "Registrar", "enrolment queue", "seat conflict"),
    ("sensor-calibration", "field engineer", "calibration run", "drift alert"),
    ("grant-review", "review chair", "grant packet", "missing appendix"),
    ("order-forecast", "demand planner", "forecast batch", "late signal"),
    ("access-badge", "security lead", "badge roster", "revoked badge"),
    ("nutrition-plan", "care coordinator", "meal plan", "allergy flag"),
    ("archive-export", "records lead", "archive export", "retention hold"),
    ("invoice-dispute", "billing lead", "dispute queue", "duplicate charge"),
    ("water-quality", "site chemist", "test report", "sample variance"),
    ("parcel-locker", "locker operator", "locker map", "door fault"),
    ("travel-approval", "travel desk", "approval form", "budget ceiling"),
    ("content-release", "editorial lead", "release checklist", "rights exception"),
    ("power-meter", "grid operator", "meter feed", "reading gap"),
    ("insurance-renewal", "underwriting lead", "renewal packet", "policy lapse"),
    ("library-loan", "library desk", "loan ledger", "overdue item"),
    ("farm-supply", "field buyer", "supply order", "delivery variance"),
    ("legal-hold", "legal ops", "hold register", "custody gap"),
    ("hotel-maintenance", "property lead", "maintenance board", "room outage"),
    ("rail-ticket", "station ops", "ticket ledger", "fare mismatch"),
)


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _source_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _entity(label: str, entity_type: str, text: str, entity_number: int) -> dict[str, Any]:
    start = text.index(label)
    return {
        "id": f"entity-{entity_number:02d}",
        "type": entity_type,
        "label": label,
        "span": {"start": start, "end": start + len(label), "text": label},
    }


def _note(case_number: int, scenario_number: int, split: str, language: str, text: str, entities: list[tuple[str, str]], relation: tuple[str, str, str] | None = None, abstention: str | None = None) -> dict[str, Any]:
    gold_entities = [_entity(label, entity_type, text, index) for index, (label, entity_type) in enumerate(entities, start=1)]
    entity_by_label = {entity["label"]: entity["id"] for entity in gold_entities}
    relations = []
    if relation:
        predicate, source, target = relation
        relations.append({"predicate": predicate, "sourceEntityId": entity_by_label[source], "targetEntityId": entity_by_label[target], "span": {"start": 0, "end": len(text), "text": text}})
    return {
        "caseId": f"s12-a-{case_number:04d}",
        "schemaVersion": "s12.atomic.v1",
        "journeyId": f"J{(scenario_number % 6) + 1}",
        "scenarioId": f"s12-s-{scenario_number + 200:03d}",
        "source": {
            "rawText": text,
            "language": language,
            "origin": "agent-authored-synthetic",
            "sensitivity": "synthetic",
            "license": "Projecta-internal-synthetic-v3-scale",
            "permissionRef": "sprint12-r14-scale-v1",
            "contentDigest": _source_digest(text),
            "authoringNote": "R14 scale track derived from approved v3 pilot patterns; pending R15 freeze.",
        },
        "split": split,
        "gold": {
            "entities": gold_entities,
            "relations": relations,
            "links": [],
            "abstention": {"required": abstention is not None, "reason": abstention},
            "semanticGaps": [],
        },
    }


def _case_text(position: int, language: str, domain: tuple[str, str, str, str], predicate: str) -> tuple[str, list[tuple[str, str]], tuple[str, str, str] | None, str | None]:
    slug, actor, artifact, risk = domain
    if language == "vi" or language == "mixed":
        decision = f"{actor} đã approve {artifact} cho {slug}."
        decision_label = f"{artifact} cho {slug}"
    else:
        decision = f"{actor} approved {artifact} for {slug}."
        decision_label = f"{artifact} for {slug}"
    if position == 1:
        if language == "vi":
            label = f"Hạng mục {slug}"
            return f"{label} phải chốt trước ca bàn giao.", [(label, "Requirement")], None, None
        return f"The {artifact} for {slug} must be locked before handover.", [({"en": f"the {artifact}", "ja": f"{artifact}"}.get(language, f"the {artifact}"), "Requirement")], None, None
    if position == 2:
        if language == "vi":
            label = f"hạng mục cho {slug}"
            return f"Nhóm phụ trách đã duyệt {label}.", [(label, "Decision")], None, None
        return decision, [(decision_label, "Decision")], None, None
    if position == 3:
        source = f"{artifact} worker"
        target = risk
        if language == "mixed":
            text = f"{source} hỗ trợ {target} nhưng vẫn {predicate} trong {slug}."
        elif language == "vi":
            source = f"tác vụ {slug}"
            target = f"rủi ro {slug}"
            text = f"{source} vẫn {predicate} {target} trong ca này."
        else:
            text = f"The {source} {predicate} the {target} for {slug}."
        return text, [(source, "Task"), (target, "Risk")], (predicate, source, target), None
    if position == 4:
        if language == "vi":
            text = f"Ai sẽ xác nhận hạng mục của {slug} sau khi chạy?"
        else:
            text = f"Who will confirm the {artifact} for {slug} after the run?"
        return text, [(text, "Question")], None, None
    if position == 5 and language == "ja":
        text = f"案件 {slug} の確認は完了しました。"
        return text, [(text, "ProgressClaim")], None, None
    if position == 5:
        text = f"The {artifact} for {slug} completed with no open handover item."
        return text, [(text, "ProgressClaim")], None, None
    if position == 6:
        if language == "vi":
            text = f"Nếu {risk} kéo dài, {slug} có thể trễ lịch bàn giao."
        else:
            text = f"A prolonged {risk} could delay the {slug} handover."
        return text, [(text, "Risk")], None, None
    if position == 7:
        source = f"{actor} review"
        target = f"{slug} control"
        if language == "vi":
            source = f"kiểm tra {slug}"
            target = f"kiểm soát {slug}"
            text = f"{source} bị giới hạn bởi {target} trong đợt này."
        elif language == "mixed":
            text = f"{source} bị giới hạn bởi {target} trong đợt này."
        else:
            text = f"The {source} is constrained by the {target} for {slug}."
        return text, [(source, "Task"), (target, "Constraint")], ("constrainedBy", source, target), None
    if language == "mixed":
        text = f"Có nên đổi {artifact} của {slug} không? Chưa có owner chốt."
    elif language == "vi":
        text = f"Có nên đổi hạng mục của {slug} không? Chưa có người phụ trách chốt."
    else:
        text = f"Should we change the {artifact} for {slug}? No owner has decided."
    return text, [], None, "unresolved choice without an owner decision"


def build_atomic() -> dict[str, Any]:
    cases = []
    case_number = 4001
    for scenario_number, domain in enumerate(DOMAINS, start=1):
        split = "development" if scenario_number <= 20 else "validation"
        languages = LANGUAGE_A if scenario_number <= 15 else LANGUAGE_B
        for position, language in enumerate(languages, start=1):
            effective_language = (
                "mixed"
                if position == 7 and domain[0] in {"grant-review", "content-release"}
                else language
            )
            predicate = PREDICATES[(scenario_number + position) % len(PREDICATES)]
            text, entities, relation, abstention = _case_text(position, effective_language, domain, predicate)
            cases.append(_note(case_number, scenario_number, split, effective_language, text, entities, relation, abstention))
            case_number += 1
    return {
        "datasetVersion": "s12.corpus.atomic.v3.scale",
        "status": "SCALE_AUTHORED_PENDING_QA",
        "authoringTrack": "agent-authored-synthetic",
        "humanEvidence": False,
        "approvedPatternSource": "s12.g31-b-pilot-approval.v1",
        "cases": cases,
    }


def build_atomic_manifest(dataset: dict[str, Any]) -> dict[str, Any]:
    cases = dataset["cases"]
    entries = [{"caseId": case["caseId"], "scenarioId": case["scenarioId"], "journeyId": case["journeyId"], "split": case["split"], "language": case["source"]["language"], "origin": case["source"]["origin"], "contentDigest": case["source"]["contentDigest"], "caseDigest": _digest(case)} for case in cases]
    manifest = {
        "manifestVersion": "s12.corpus.manifest.v3.scale",
        "datasetVersion": dataset["datasetVersion"],
        "status": dataset["status"],
        "humanEvidence": False,
        "qualifiedHumanEvidence": False,
        "atomicCounts": {
            "development": sum(case["split"] == "development" for case in cases),
            "validation": sum(case["split"] == "validation" for case in cases),
            "test": 0,
            "total": len(cases),
        },
        "atomicCases": entries,
        "permissionRef": "sprint12-r14-scale-v1",
        "testPayloadPresent": False,
        "approvedPatternSource": "s12.g31-b-pilot-approval.v1",
    }
    manifest["manifestDigest"] = _digest(manifest)
    return manifest


def build_scenarios(dataset: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for case in dataset["cases"]:
        by_scenario.setdefault(case["scenarioId"], []).append(case)
    scenarios = []
    for scenario_number in range(1, len(DOMAINS) + 1):
        scenario_id = f"s12-s-{scenario_number + 200:03d}"
        cases = by_scenario[scenario_id]
        events = []
        for sequence, case in enumerate(cases, start=1):
            effects = ("creates", "creates", "updates", "none", "updates", "contradicts", "updates", "supersedes")
            dispositions = ("confirmed", "confirmed", "confirmed", "deferred", "confirmed", "rejected", "confirmed", "deferred")
            correction = ("unchanged", "unchanged", "minor-semantic", "not-applicable", "unchanged", "rejected", "formatting-only", "major-semantic")
            events.append({"eventId": f"event-{sequence:02d}", "sequence": sequence, "caseId": case["caseId"], "expectedTemporalEffect": effects[sequence - 1], "expectedReview": {"disposition": dispositions[sequence - 1], "correctionClass": correction[sequence - 1], "rationale": f"The project owner reviews {case['caseId']} after sequence {sequence}; the decision preserves chronology and records the current business state."}})
        checkpoints = []
        for after in (2, 4, 6, 8):
            checkpoints.append({"afterSequence": after, "sourceIds": [case["caseId"] for case in cases[:after]], "candidateIds": [f"candidate-{scenario_number:02d}-{index:02d}" for index in range(1, after + 1)], "assertedIds": [f"asserted-{scenario_number:02d}-01"], "inferredExpectations": ["history-preserved"] + (["open-review-risk"] if after >= 6 else []), "provenanceActivityIds": [f"activity-{scenario_number:02d}-{index:02d}" for index in range(1, after + 1)], "contradictionIds": [f"contradiction-{scenario_number:02d}-01"] if after >= 6 else []})
        scenarios.append({"scenarioId": scenario_id, "schemaVersion": "s12.scenario.v1", "journeyId": cases[0]["journeyId"], "split": cases[0]["split"], "events": events, "checkpoints": checkpoints, "competencyAnswers": [{"questionId": f"CQ-{scenario_number:02d}", "status": "answerable", "expectedFactIds": [f"fact-{scenario_number:02d}-01"], "expectedCitationIds": [cases[0]["caseId"]], "completeness": "complete", "freshness": "current", "abstain": False}, {"questionId": f"CQ-{scenario_number + 25:02d}", "status": "ambiguous", "expectedFactIds": [], "expectedCitationIds": [cases[-1]["caseId"]], "completeness": "not-applicable", "freshness": "not-applicable", "abstain": True}], "sourceManifest": [case["caseId"] for case in cases]})
    dataset_payload = {"datasetVersion": "s12.corpus.scenario.v3.scale", "status": "SCALE_AUTHORED_PENDING_QA", "authoringTrack": "agent-authored-synthetic", "humanEvidence": False, "atomicDatasetVersion": dataset["datasetVersion"], "approvedPatternSource": "s12.g31-b-pilot-approval.v1", "scenarios": scenarios}
    manifest = {"manifestVersion": "s12.corpus.scenario-manifest.v3.scale", "datasetVersion": dataset_payload["datasetVersion"], "atomicDatasetVersion": dataset["datasetVersion"], "status": dataset_payload["status"], "humanEvidence": False, "scenarioCounts": {"development": sum(scenario["split"] == "development" for scenario in scenarios), "validation": sum(scenario["split"] == "validation" for scenario in scenarios), "test": 0, "total": len(scenarios)}, "scenarios": [{"scenarioId": scenario["scenarioId"], "journeyId": scenario["journeyId"], "split": scenario["split"], "sourceManifest": scenario["sourceManifest"], "scenarioDigest": _digest(scenario)} for scenario in scenarios], "testPayloadPresent": False, "approvedPatternSource": "s12.g31-b-pilot-approval.v1"}
    manifest["manifestDigest"] = _digest(manifest)
    return dataset_payload, manifest


def write_all(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic = build_atomic()
    atomic_manifest = build_atomic_manifest(atomic)
    scenarios, scenario_manifest = build_scenarios(atomic)
    files = {"atomic-scale.v1.json": atomic, "manifest-scale.v1.json": atomic_manifest, "scenario-scale.v1.json": scenarios, "scenario-manifest-scale.v1.json": scenario_manifest}
    for name, payload in files.items():
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"atomic": len(atomic["cases"]), "scenarios": len(scenarios["scenarios"]), "development": atomic_manifest["atomicCounts"]["development"], "validation": atomic_manifest["atomicCounts"]["validation"], "test": 0}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_all(args.output_dir)


if __name__ == "__main__":
    main()
