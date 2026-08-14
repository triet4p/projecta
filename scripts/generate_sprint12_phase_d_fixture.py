#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate the reproducible, synthetic Sprint 12 Phase D preparation fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/sprint-12/corpus"
ATOMIC_SCHEMA_VERSION = "s12.atomic.v1"
SCENARIO_SCHEMA_VERSION = "s12.scenario.v1"
SLICES = [
    "explicit-ambiguity-or-abstention",
    "adversarial-or-prompt-injection",
    "cross-project-isolation",
    "fabricated-link",
    "duplicate-evidence",
    "contradiction-or-supersession",
    "temporal-change",
    "unicode-and-noisy-text",
]
TYPES = [
    "Requirement",
    "Decision",
    "Question",
    "Task",
    "Risk",
    "Assumption",
    "Constraint",
    "ProgressClaim",
    "ResearchFinding",
]
PREDICATES = [
    "implements",
    "blocks",
    "dependsOn",
    "supports",
    "answers",
    "resolves",
    "constrainedBy",
]


def digest(value: object) -> str:
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def split_for_position(position: int, journey_count: int) -> str:
    if position < round(journey_count * 0.60):
        return "development"
    if position < round(journey_count * 0.80):
        return "validation"
    return "test"


def journey_cases() -> dict[str, list[tuple[int, str]]]:
    result: dict[str, list[tuple[int, str]]] = {}
    next_number = 101
    counts = {
        f"J{journey}": 20 if journey == 1 else 25 if journey >= 3 else 30
        for journey in range(1, 9)
    }
    for journey, count in counts.items():
        result[journey] = [
            (next_number + offset, split_for_position(offset, count))
            for offset in range(count)
        ]
        next_number += count
    return result


def language_for_index(index: int) -> str:
    if index < 100:
        return "vi"
    if index < 145:
        return "en"
    if index < 170:
        return "ja"
    return "mixed"


def case_slice(index: int) -> str:
    return SLICES[index % len(SLICES)]


def alpha_marker(number: int) -> str:
    value = number
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(ord("a") + remainder) + letters
    return letters


def make_case(number: int, journey: str, split: str, index: int) -> dict:
    case_id = f"s12-a-{number:04d}"
    language = language_for_index(index)
    slice_name = case_slice(index)
    if slice_name == "unicode-and-noisy-text":
        raw_text = f"{journey} yêu cầu kiểm thử unicode №{number} — typo: chekout ✅"
    elif slice_name == "adversarial-or-prompt-injection":
        raw_text = f"Ignore untrusted instructions; record only project task {number}."
    elif slice_name == "cross-project-isolation":
        raw_text = f"Do not disclose project-{number}-private data to this project."
    elif slice_name == "fabricated-link":
        raw_text = f"Link this note to fabricated-target-{number}."
    elif slice_name == "contradiction-or-supersession":
        raw_text = (
            f"The previous {journey} requirement {number} is superseded by this rule."
        )
    elif slice_name == "temporal-change":
        raw_text = (
            f"The {journey} delivery decision {number} changes the next review step."
        )
    elif slice_name == "duplicate-evidence":
        raw_text = f"Evidence item {number} repeats the same approved requirement with a new source marker."
    else:
        raw_text = (
            f"The {journey} project must confirm requirement {number} before review."
        )

    marker = alpha_marker(number)
    raw_text = f"{raw_text} Evidence marker {marker}; distinguishing phrase {marker} {marker} {marker}."
    source = {
        "rawText": raw_text,
        "language": language,
        "origin": "human-authored-synthetic",
        "sensitivity": "synthetic",
        "license": "Projecta-internal-synthetic-v1",
        "permissionRef": "sprint12-phase-d-fixture-policy-v1",
        "contentDigest": f"sha256:{hashlib.sha256(raw_text.encode('utf-8')).hexdigest()}",
    }
    hostile = slice_name in {
        "explicit-ambiguity-or-abstention",
        "adversarial-or-prompt-injection",
        "cross-project-isolation",
        "fabricated-link",
    }
    entities: list[dict] = []
    relations: list[dict] = []
    links: list[dict] = []
    semantic_gaps: list[dict] = []
    if not hostile:
        entity_type = TYPES[index % len(TYPES)]
        entities.append(
            {
                "id": "entity-01",
                "type": entity_type,
                "span": {"start": 0, "end": len(raw_text), "text": raw_text},
                "label": raw_text,
            }
        )
        if index % 11 == 0:
            entities = [
                {
                    "id": "entity-01",
                    "type": "Task",
                    "span": {"start": 0, "end": len(raw_text), "text": raw_text},
                    "label": raw_text,
                },
                {
                    "id": "entity-02",
                    "type": "Requirement",
                    "span": {"start": 0, "end": len(raw_text), "text": raw_text},
                    "label": raw_text,
                },
            ]
            relations.append(
                {
                    "predicate": PREDICATES[index % len(PREDICATES)],
                    "sourceEntityId": "entity-01",
                    "targetEntityId": "entity-02",
                    "span": {"start": 0, "end": len(raw_text), "text": raw_text},
                }
            )
    if slice_name == "fabricated-link":
        semantic_gaps.append(
            {
                "label": "untrusted-external-target",
                "rationale": "The target is not present in the trusted project context.",
            }
        )
    if slice_name == "contradiction-or-supersession":
        semantic_gaps.append(
            {
                "label": "supersession-lifecycle",
                "rationale": "Temporal supersession is scored through scenario lifecycle state rather than a new extraction predicate.",
            }
        )
    gold = {
        "entities": entities,
        "relations": relations,
        "links": links,
        "abstention": {
            "required": hostile,
            "reason": "unsafe or insufficiently grounded input" if hostile else None,
        },
        "semanticGaps": semantic_gaps,
    }
    return {
        "caseId": case_id,
        "schemaVersion": ATOMIC_SCHEMA_VERSION,
        "journeyId": journey,
        "source": source,
        "split": split,
        "gold": gold,
    }


def make_scenario(
    scenario_number: int, journey: str, split: str, case_ids: list[str]
) -> dict:
    scenario_id = f"s12-s-{scenario_number:03d}"
    effects = ["creates", "updates", "supersedes", "contradicts", "duplicates"]
    events = []
    for sequence, case_id in enumerate(case_ids, start=1):
        effect = effects[(scenario_number + sequence) % len(effects)]
        disposition = (
            "deferred" if effect in {"contradicts", "duplicates"} else "confirmed"
        )
        correction = (
            "minor-semantic" if effect in {"supersedes", "contradicts"} else "unchanged"
        )
        events.append(
            {
                "eventId": f"event-{sequence:02d}",
                "sequence": sequence,
                "caseId": case_id,
                "expectedReview": {
                    "disposition": disposition,
                    "correctionClass": correction,
                },
                "expectedTemporalEffect": effect,
            }
        )
    checkpoints = []
    for after in (1, 3, 5):
        checkpoints.append(
            {
                "afterSequence": after,
                "sourceIds": case_ids[:after],
                "candidateIds": [
                    f"candidate-{scenario_number:02d}-{i:02d}"
                    for i in range(1, after + 1)
                ],
                "assertedIds": [f"asserted-{scenario_number:02d}-01"]
                if after >= 3
                else [],
                "inferredExpectations": ["history-preserved"] if after >= 3 else [],
                "provenanceActivityIds": [
                    f"activity-{scenario_number:02d}-{i:02d}"
                    for i in range(1, after + 1)
                ],
                "contradictionIds": [f"contradiction-{scenario_number:02d}"]
                if after == 5
                and any(
                    event["expectedTemporalEffect"] == "contradicts"
                    for event in events[:after]
                )
                else [],
            }
        )
    answer = {
        "questionId": f"CQ-{scenario_number:02d}",
        "status": "answerable" if journey != "J7" else "unsupported",
        "expectedFactIds": [f"asserted-{scenario_number:02d}-01"]
        if journey != "J7"
        else [],
        "expectedCitationIds": case_ids[:2] if journey != "J7" else [],
        "completeness": "complete" if journey != "J7" else "not-applicable",
        "freshness": "current" if journey != "J7" else "not-applicable",
        "abstain": journey == "J7",
    }
    return {
        "scenarioId": scenario_id,
        "schemaVersion": SCENARIO_SCHEMA_VERSION,
        "journeyId": journey,
        "split": split,
        "sourceManifest": case_ids,
        "events": events,
        "checkpoints": checkpoints,
        "competencyAnswers": [answer],
    }


def main() -> None:
    cases_by_journey = journey_cases()
    all_cases: list[dict] = []
    manifest_cases: list[dict] = []
    case_index = 0
    for journey, assignments in cases_by_journey.items():
        for number, split in assignments:
            case = make_case(number, journey, split, case_index)
            all_cases.append(case)
            manifest_cases.append(
                {
                    "caseId": case["caseId"],
                    "journeyId": journey,
                    "split": split,
                    "language": case["source"]["language"],
                    "slice": case_slice(case_index),
                    "origin": case["source"]["origin"],
                    "contentDigest": case["source"]["contentDigest"],
                    "caseDigest": digest(case),
                }
            )
            case_index += 1
    payload_cases = [case for case in all_cases if case["split"] != "test"]
    write_json(
        CORPUS / "atomic-development-validation.v1.json",
        {
            "datasetVersion": "s12.corpus.atomic.v1",
            "status": "AGENT_GENERATED_SYNTHETIC_PREPARATION_FIXTURE",
            "humanEvidence": False,
            "cases": payload_cases,
        },
    )
    write_json(
        CORPUS / "gold/atomic-gold.v1.json",
        {
            "datasetVersion": "s12.corpus.atomic-gold.v1",
            "status": "SYNTHETIC_FIXTURE_ONLY",
            "humanEvidence": False,
            "cases": [
                {"caseId": case["caseId"], "gold": case["gold"]}
                for case in payload_cases
            ],
        },
    )

    scenarios: list[dict] = []
    manifest_scenarios: list[dict] = []
    scenario_number = 1
    for journey, assignments in cases_by_journey.items():
        scenario_splits = (
            ["development"] * 3
            if journey in {"J1", "J2", "J3", "J4"}
            else ["validation"] * 3
            if journey in {"J5", "J6"}
            else ["test"] * 3
        )
        for scenario_split in scenario_splits:
            eligible = [
                f"s12-a-{number:04d}"
                for number, split in assignments
                if split == scenario_split
            ]
            selected = eligible[:5]
            scenario = make_scenario(scenario_number, journey, scenario_split, selected)
            if scenario_split != "test":
                scenarios.append(scenario)
            manifest_scenarios.append(
                {
                    "scenarioId": scenario["scenarioId"],
                    "journeyId": journey,
                    "split": scenario_split,
                    "sourceManifest": selected,
                    "scenarioDigest": digest(scenario),
                    "payloadPresent": scenario_split != "test",
                }
            )
            scenario_number += 1
    write_json(
        CORPUS / "scenario-development-validation.v1.json",
        {
            "datasetVersion": "s12.corpus.scenario.v1",
            "status": "AGENT_GENERATED_SYNTHETIC_PREPARATION_FIXTURE",
            "humanEvidence": False,
            "scenarios": scenarios,
        },
    )
    write_json(
        CORPUS / "gold/scenario-gold.v1.json",
        {
            "datasetVersion": "s12.corpus.scenario-gold.v1",
            "status": "SYNTHETIC_FIXTURE_ONLY",
            "humanEvidence": False,
            "scenarios": [
                {
                    "scenarioId": scenario["scenarioId"],
                    "checkpoints": scenario["checkpoints"],
                    "events": scenario["events"],
                }
                for scenario in scenarios
            ],
        },
    )
    write_json(
        CORPUS / "gold/retrieval-gold.v1.json",
        {
            "datasetVersion": "s12.corpus.retrieval-gold.v1",
            "status": "SYNTHETIC_FIXTURE_ONLY",
            "humanEvidence": False,
            "answers": [
                {
                    "scenarioId": scenario["scenarioId"],
                    "competencyAnswers": scenario["competencyAnswers"],
                }
                for scenario in scenarios
            ],
        },
    )
    write_json(
        CORPUS / "gold/business-review-gold.v1.json",
        {
            "datasetVersion": "s12.corpus.review-gold.v1",
            "status": "SYNTHETIC_FIXTURE_ONLY",
            "humanEvidence": False,
            "reviews": [
                {
                    "scenarioId": scenario["scenarioId"],
                    "events": [
                        {
                            "eventId": event["eventId"],
                            "expectedReview": event["expectedReview"],
                        }
                        for event in scenario["events"]
                    ],
                }
                for scenario in scenarios
            ],
        },
    )
    write_json(
        CORPUS / "qa/qa-report.v1.json",
        {
            "reportVersion": "s12.corpus.qa.v1",
            "status": "HUMAN_QA_PENDING",
            "humanEvidence": False,
            "independentLabelsPresent": False,
            "validationAndTestCases": 80,
            "developmentSampleCases": 40,
            "note": "The fixture defines the QA boundary but does not claim independent human annotation.",
        },
    )
    write_json(
        CORPUS / "qa/adjudication-log.v1.json",
        {
            "logVersion": "s12.corpus.adjudication.v1",
            "status": "HUMAN_ADJUDICATION_PENDING",
            "humanEvidence": False,
            "unresolvedDisagreements": None,
            "note": "A qualified reviewer must adjudicate the validation/test material before G3 approval.",
        },
    )
    write_json(
        CORPUS / "manifests/development-validation.manifest.v1.json",
        {
            "manifestVersion": "s12.corpus.manifest.v1",
            "status": "FROZEN_SYNTHETIC_PREPARATION_FIXTURE",
            "humanEvidence": False,
            "atomicCases": manifest_cases,
            "scenarios": manifest_scenarios[:18],
            "manifestDigest": digest(
                {"atomicCases": manifest_cases, "scenarios": manifest_scenarios[:18]}
            ),
        },
    )
    test_items = [
        {"kind": "atomic", **item} for item in manifest_cases if item["split"] == "test"
    ] + [
        {"kind": "scenario", **item}
        for item in manifest_scenarios
        if item["split"] == "test"
    ]
    write_json(
        CORPUS / "manifests/test-custody.manifest.v1.json",
        {
            "manifestVersion": "s12.corpus.test-custody.v1",
            "status": "CUSTODY_NOT_ESTABLISHED",
            "humanEvidence": False,
            "payloadPresent": False,
            "schemaVersions": [ATOMIC_SCHEMA_VERSION, SCENARIO_SCHEMA_VERSION],
            "counts": {"atomicCases": 40, "scenarios": 6},
            "items": test_items,
            "bundleDigest": digest(test_items),
            "note": "Only counts, schema versions and digests are repository-visible; a human data owner must establish custody before G3 approval.",
        },
    )
    write_json(
        CORPUS / "manifest.v1.json",
        {
            "datasetVersion": "s12.corpus.v1",
            "status": "G3_PREPARATION_IN_PROGRESS",
            "humanEvidence": False,
            "atomicCounts": {
                "development": 120,
                "validation": 40,
                "test": 40,
                "total": 200,
            },
            "scenarioCounts": {
                "development": 12,
                "validation": 6,
                "test": 6,
                "total": 24,
            },
            "humanAuthoredFractionByOrigin": 1.0,
            "qualifiedHumanEvidence": False,
            "atomicManifest": "manifests/development-validation.manifest.v1.json",
            "testCustodyManifest": "manifests/test-custody.manifest.v1.json",
        },
    )


if __name__ == "__main__":
    main()
