#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Validate the repository-visible Sprint 12 Phase D preparation fixture."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/sprint-12/corpus"
SLICES = {
    "explicit-ambiguity-or-abstention",
    "adversarial-or-prompt-injection",
    "cross-project-isolation",
    "fabricated-link",
    "duplicate-evidence",
    "contradiction-or-supersession",
    "temporal-change",
    "unicode-and-noisy-text",
}
HOSTILE_SLICES = {
    "explicit-ambiguity-or-abstention",
    "adversarial-or-prompt-injection",
    "cross-project-isolation",
    "fabricated-link",
}
RELEASED_TYPES = {
    "Requirement",
    "Decision",
    "Question",
    "Task",
    "Risk",
    "Assumption",
    "Constraint",
    "ProgressClaim",
    "ResearchFinding",
}
RELEASED_PREDICATES = {
    "implements",
    "blocks",
    "dependsOn",
    "supports",
    "answers",
    "resolves",
    "constrainedBy",
}
REQUIRED_ATOMIC = {"caseId", "schemaVersion", "journeyId", "source", "split", "gold"}
REQUIRED_SCENARIO = {
    "scenarioId",
    "schemaVersion",
    "journeyId",
    "split",
    "sourceManifest",
    "events",
    "checkpoints",
    "competencyAnswers",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_digest(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def validate_atomic(payload: dict, manifest: dict) -> None:
    cases = payload["cases"]
    entries = manifest["atomicCases"]
    assert len(cases) == 160
    assert len(entries) == 200
    assert {case["caseId"] for case in cases} == {
        entry["caseId"] for entry in entries if entry["split"] != "test"
    }
    assert Counter(case["split"] for case in entries) == Counter(
        {"development": 120, "validation": 40, "test": 40}
    )
    assert Counter(entry["journeyId"] for entry in entries) == Counter(
        {"J1": 20, "J2": 30, "J3": 25, "J4": 25, "J5": 25, "J6": 25, "J7": 25, "J8": 25}
    )
    assert Counter(entry["language"] for entry in entries) >= Counter(
        {"vi": 80, "en": 40, "ja": 20, "mixed": 20}
    )
    assert {entry["slice"] for entry in entries} == SLICES
    assert all(
        case["schemaVersion"] == "s12.atomic.v1" and REQUIRED_ATOMIC <= case.keys()
        for case in cases
    )
    by_id = {case["caseId"]: case for case in cases}
    for entry in entries:
        if entry["split"] == "test":
            continue
        case = by_id[entry["caseId"]]
        source = case["source"]
        raw_text = source["rawText"]
        assert (
            source["contentDigest"]
            == f"sha256:{hashlib.sha256(raw_text.encode('utf-8')).hexdigest()}"
        )
        assert entry["contentDigest"] == source["contentDigest"]
        assert entry["caseDigest"] == canonical_digest(case)
        for item in (
            case["gold"]["entities"] + case["gold"]["relations"] + case["gold"]["links"]
        ):
            span = item["span"]
            assert source["rawText"][span["start"] : span["end"]] == span["text"]
            assert span["start"] < span["end"]
    assert len({entry["contentDigest"] for entry in entries}) == len(entries)


def validate_scenarios(payload: dict, manifest: dict) -> None:
    scenarios = payload["scenarios"]
    entries = manifest["scenarios"]
    assert len(entries) == 18
    assert Counter(
        entry["split"] for entry in manifest["scenarios"] + [{"split": "test"}] * 6
    ) == Counter({"development": 12, "validation": 6, "test": 6})
    assert len({entry["journeyId"] for entry in entries}) == 6
    assert all(
        scenario["schemaVersion"] == "s12.scenario.v1"
        and REQUIRED_SCENARIO <= scenario.keys()
        for scenario in scenarios
    )
    scenario_ids = {scenario["scenarioId"] for scenario in scenarios}
    assert {entry["scenarioId"] for entry in entries} == scenario_ids
    atomic_manifest = read_json(
        CORPUS / "manifests/development-validation.manifest.v1.json"
    )["atomicCases"]
    available = {entry["caseId"] for entry in atomic_manifest}
    for scenario in scenarios:
        assert len(scenario["events"]) == 5
        event_ids = [event["caseId"] for event in scenario["events"]]
        assert scenario["sourceManifest"] == event_ids
        assert set(event_ids) <= available
        assert len(scenario["checkpoints"]) == 3
        assert scenario["competencyAnswers"]


def validate_privacy(manifest: dict, payload: dict) -> None:
    assert manifest["qualifiedHumanEvidence"] is False
    assert manifest["humanAuthoredFractionByOrigin"] == 0.0
    forbidden = re.compile(
        r"(?i)(api[_ -]?key|password|secret|bearer|token=|@example\.)"
    )
    for case in payload["cases"]:
        assert case["source"]["sensitivity"] == "synthetic"
        assert case["source"]["origin"] == "agent-authored-synthetic"
        assert "not human-authored evidence" in case["source"]["authoringNote"]
        assert not forbidden.search(case["source"]["rawText"])


def validate_semantic_gold(payload: dict, manifest: dict) -> None:
    slice_by_case = {
        entry["caseId"]: entry["slice"] for entry in manifest["atomicCases"]
    }
    observed_types: set[str] = set()
    observed_predicates: set[str] = set()
    for case in payload["cases"]:
        gold = case["gold"]
        source = case["source"]["rawText"]
        slice_name = slice_by_case[case["caseId"]]
        entity_ids = {entity["id"] for entity in gold["entities"]}
        if slice_name in HOSTILE_SLICES:
            assert gold["abstention"]["required"] is True
            assert not gold["entities"]
            assert not gold["relations"]
            assert not gold["links"]
        else:
            assert gold["abstention"] == {"required": False, "reason": None}
            assert gold["entities"]
        for entity in gold["entities"]:
            observed_types.add(entity["type"])
            span = entity["span"]
            assert source[span["start"] : span["end"]] == span["text"]
            assert span["text"] == entity["label"]
            assert "Evidence marker" not in span["text"]
        for relation in gold["relations"]:
            observed_predicates.add(relation["predicate"])
            assert relation["sourceEntityId"] in entity_ids
            assert relation["targetEntityId"] in entity_ids
            assert relation["sourceEntityId"] != relation["targetEntityId"]
            span = relation["span"]
            assert source[span["start"] : span["end"]] == span["text"]
        if slice_name == "contradiction-or-supersession":
            assert gold["semanticGaps"] == [
                {
                    "label": "candidate-contract-supersedes",
                    "rationale": "The released ontology supports supersession, but the atomic candidate relation allowlist does not expose it; lifecycle scoring remains scenario-level.",
                    "candidateReleasedTerm": "supersedes",
                }
            ]
        else:
            assert not gold["semanticGaps"]
    assert observed_types == RELEASED_TYPES
    assert observed_predicates == RELEASED_PREDICATES


def validate_owner_delegated_ai_review(payload: dict, scenarios: dict) -> None:
    review = read_json(CORPUS / "qa/owner-delegated-ai-review.v1.json")
    qa = read_json(CORPUS / "qa/qa-report.v1.json")
    adjudication = read_json(CORPUS / "qa/adjudication-log.v1.json")
    assert review["status"] == "COMPLETE_FOR_SYNTHETIC_AI_TRACK"
    assert review["reviewerKind"] == "ai-agent"
    assert review["humanEvidence"] is False
    assert {item["caseId"] for item in review["atomicReviews"]} == {
        case["caseId"] for case in payload["cases"]
    }
    assert {item["scenarioId"] for item in review["scenarioReviews"]} == {
        scenario["scenarioId"] for scenario in scenarios["scenarios"]
    }
    assert qa["status"] == "OWNER_DELEGATED_AI_QA_COMPLETE"
    assert qa["ownerDelegatedAiReviewPresent"] is True
    assert qa["independentLabelsPresent"] is False
    assert adjudication["status"] == "OWNER_DELEGATED_AI_ADJUDICATION_COMPLETE"
    assert adjudication["unresolvedDisagreements"] == 0
    assert adjudication["independentHumanAdjudication"] is False


def validate_leakage(payload: dict, manifest: dict) -> None:
    texts = [case["source"]["rawText"] for case in payload["cases"]]
    assert len(texts) == len(set(texts))
    normalized = [re.sub(r"\d+", "#", text.lower()) for text in texts]
    for index, text in enumerate(normalized):
        for other in normalized[index + 1 :]:
            assert SequenceMatcher(None, text, other).ratio() < 0.98
    assert len({entry["caseDigest"] for entry in manifest["atomicCases"]}) == len(
        manifest["atomicCases"]
    )


def validate_custody() -> None:
    custody = read_json(CORPUS / "manifests/test-custody.manifest.v1.json")
    assert custody["status"] == "CUSTODY_NOT_ESTABLISHED"
    assert custody["payloadPresent"] is False
    assert custody["reconstructibleFromRepository"] is True
    assert custody["eligibleForHeldOut"] is False
    assert custody["counts"] == {"atomicCases": 40, "scenarios": 6}
    assert not (CORPUS / "test").exists()


def validate() -> dict[str, object]:
    payload = read_json(CORPUS / "atomic-development-validation.v1.json")
    manifest = read_json(CORPUS / "manifest.v1.json")
    dev_validation = read_json(
        CORPUS / "manifests/development-validation.manifest.v1.json"
    )
    scenario_payload = read_json(CORPUS / "scenario-development-validation.v1.json")
    validate_atomic(payload, dev_validation)
    validate_scenarios(scenario_payload, dev_validation)
    validate_privacy(manifest, payload)
    validate_semantic_gold(payload, dev_validation)
    validate_owner_delegated_ai_review(payload, scenario_payload)
    validate_leakage(payload, dev_validation)
    validate_custody()
    return {
        "status": "PASS_WITH_OWNER_DELEGATED_AI_REVIEW",
        "atomicPayloadCases": 160,
        "atomicManifestCases": 200,
        "scenarioPayloadEpisodes": 18,
        "scenarioManifestEpisodes": 24,
        "testCustody": "not-established",
        "humanEvidence": False,
        "ownerDelegatedAiReview": True,
    }


if __name__ == "__main__":
    report = validate()
    report.update(
        {
            "reportVersion": "s12.corpus.validation.v1",
            "validationScope": "repository-visible development/validation fixture and test custody metadata",
        }
    )
    (CORPUS / "validation").mkdir(parents=True, exist_ok=True)
    (CORPUS / "validation/report.v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
