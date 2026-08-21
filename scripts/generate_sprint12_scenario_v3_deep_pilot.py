#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate six unique Sprint 12 longitudinal v3 deep-pilot episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/corpus/v3"
ATOMIC_PATH = DEFAULT_OUTPUT / "atomic-deep-pilot.v1.json"


def _event(
    effect: str,
    disposition: str,
    correction: str,
    rationale: str,
) -> dict[str, str]:
    return {
        "expectedTemporalEffect": effect,
        "disposition": disposition,
        "correctionClass": correction,
        "rationale": rationale,
    }


EPISODES = [
    {
        "scenarioId": "s12-s-101",
        "journeyId": "J1",
        "split": "development",
        "cases": [f"s12-a-{number}" for number in range(3001, 3009)],
        "events": [
            _event("creates", "confirmed", "unchanged", "Finance lead opened the Friday close requirement during Monday planning."),
            _event("updates", "confirmed", "minor-semantic", "Treasury manager confirmed the Stripe fallback after the Tuesday retry review."),
            _event("creates", "confirmed", "unchanged", "Settlement operations recorded the missing-file risk at Wednesday stand-up."),
            _event("none", "deferred", "unchanged", "The chargeback owner was not named; the finance lead deferred assignment to Thursday."),
            _event("implements", "confirmed", "unchanged", "Platform engineer confirmed the replay mapping after the Thursday sandbox run."),
            _event("contradicts", "deferred", "minor-semantic", "Risk reviewer kept the short retry window open because the gateway response was not yet reproduced."),
            _event("updates", "confirmed", "unchanged", "Refund controller confirmed the two-hour review constraint before month close."),
            _event("none", "deferred", "unchanged", "Product owner left the old-versus-new ledger choice unresolved for the next review."),
        ],
        "answers": [
            ("CQ-01", "answerable", ["fact-101-01", "fact-101-02"], ["s12-a-3001", "s12-a-3002"], "complete", "current", False),
            ("CQ-02", "ambiguous", [], ["s12-a-3008"], "not-applicable", "not-applicable", True),
        ],
    },
    {
        "scenarioId": "s12-s-102",
        "journeyId": "J2",
        "split": "development",
        "cases": [f"s12-a-{number}" for number in range(3009, 3017)],
        "events": [
            _event("creates", "confirmed", "unchanged", "Warehouse manager set the outbound lock as the first Monday dispatch rule."),
            _event("updates", "confirmed", "minor-semantic", "Loading supervisor chose pallet scanning at Tuesday bay planning."),
            _event("creates", "deferred", "minor-semantic", "Line-B lead reported the carton-label risk and asked operations to verify it."),
            _event("none", "deferred", "unchanged", "Regional warehouse coordinator asked for an ETA; transport planner deferred the answer."),
            _event("creates", "confirmed", "unchanged", "Training lead confirmed the scanner pilot complete after Wednesday practice."),
            _event("contradicts", "deferred", "minor-semantic", "Quality reviewer marked the barcode risk as open because the pass-rate sample was incomplete."),
            _event("updates", "confirmed", "unchanged", "Slotting analyst confirmed the dependency before the next picking wave."),
            _event("none", "deferred", "unchanged", "Logistics director postponed the 3PL overflow choice until capacity numbers arrive."),
        ],
        "answers": [
            ("CQ-03", "answerable", ["fact-102-01", "fact-102-02"], ["s12-a-3009", "s12-a-3010"], "complete", "current", False),
            ("CQ-04", "ambiguous", [], ["s12-a-3016"], "not-applicable", "not-applicable", True),
        ],
    },
    {
        "scenarioId": "s12-s-103",
        "journeyId": "J3",
        "split": "development",
        "cases": [f"s12-a-{number}" for number in range(3017, 3025)],
        "events": [
            _event("creates", "confirmed", "unchanged", "Identity architect required an owner on every tenant before SSO planning started."),
            _event("updates", "confirmed", "minor-semantic", "Security lead selected OAuth device flow at the partner-portal design review."),
            _event("implements", "confirmed", "unchanged", "Migration engineer confirmed the SSO mapping in the first import rehearsal."),
            _event("none", "deferred", "unchanged", "Tenant operations asked who could approve the locked list; the release manager deferred it."),
            _event("creates", "confirmed", "unchanged", "Data migration lead confirmed the dry run completed with no rejected rows."),
            _event("contradicts", "deferred", "major-semantic", "Policy owner kept the region-mapping risk unresolved because tenant routing evidence was missing."),
            _event("updates", "confirmed", "unchanged", "Mobile security reviewer confirmed the device-binding constraint for the login flow."),
            _event("supersedes", "deferred", "major-semantic", "Product security deferred the old-login shutdown until the OAuth rollout owner signs off."),
        ],
        "answers": [
            ("CQ-05", "answerable", ["fact-103-01", "fact-103-02"], ["s12-a-3017", "s12-a-3018"], "complete", "current", False),
            ("CQ-06", "ambiguous", [], ["s12-a-3024"], "not-applicable", "not-applicable", True),
        ],
    },
    {
        "scenarioId": "s12-s-104",
        "journeyId": "J4",
        "split": "development",
        "cases": [f"s12-a-{number}" for number in range(3025, 3033)],
        "events": [
            _event("creates", "confirmed", "unchanged", "Claims product owner required an audit trail before the Monday payout planning session."),
            _event("updates", "confirmed", "minor-semantic", "Claims manager approved two-step review for high-value payouts on Tuesday."),
            _event("updates", "confirmed", "unchanged", "Fraud lead confirmed the reviewer support rule after the anomaly triage."),
            _event("none", "deferred", "unchanged", "Compliance coordinator asked for a sign-off owner; the claims manager deferred assignment."),
            _event("creates", "deferred", "minor-semantic", "Partner operations recorded two late files and asked for a delivery review."),
            _event("contradicts", "deferred", "major-semantic", "Payout controller held the VIP auto-payout decision because the policy exception was missing."),
            _event("updates", "confirmed", "unchanged", "Knowledge lead confirmed that the FAQ assistant can answer the duplicate-claim question."),
            _event("none", "deferred", "unchanged", "Claims owner kept the export scope open until the approved-claim boundary is agreed."),
        ],
        "answers": [
            ("CQ-07", "answerable", ["fact-104-01", "fact-104-02"], ["s12-a-3025", "s12-a-3026"], "complete", "current", False),
            ("CQ-08", "ambiguous", [], ["s12-a-3032"], "not-applicable", "not-applicable", True),
        ],
    },
    {
        "scenarioId": "s12-s-105",
        "journeyId": "J5",
        "split": "validation",
        "cases": [f"s12-a-{number}" for number in range(3033, 3041)],
        "events": [
            _event("creates", "confirmed", "unchanged", "Clinic operations required an urgent-follow-up buffer during Monday scheduling."),
            _event("updates", "confirmed", "minor-semantic", "Clinic manager selected SMS reminders at the Tuesday patient-flow review."),
            _event("contradicts", "deferred", "minor-semantic", "Nurse lead reported that missing consent contradicts confirmation policy and requested compliance review."),
            _event("none", "deferred", "unchanged", "Patient support asked which channel allows rescheduling; service owner deferred the answer."),
            _event("creates", "confirmed", "unchanged", "Nursing lead confirmed the reminder pilot after Wednesday shift handover."),
            _event("updates", "confirmed", "unchanged", "Consent coordinator confirmed that appointment confirmation depends on the consent check."),
            _event("updates", "confirmed", "minor-semantic", "Japanese clinic liaison confirmed the pre-visit email requirement for the validation episode."),
            _event("none", "deferred", "unchanged", "Scheduling owner postponed the single-queue choice until the clinic capacity review."),
        ],
        "answers": [
            ("CQ-09", "answerable", ["fact-105-01", "fact-105-02"], ["s12-a-3033", "s12-a-3034"], "complete", "current", False),
            ("CQ-10", "ambiguous", [], ["s12-a-3040"], "not-applicable", "not-applicable", True),
        ],
    },
    {
        "scenarioId": "s12-s-106",
        "journeyId": "J6",
        "split": "validation",
        "cases": [f"s12-a-{number}" for number in range(3041, 3049)],
        "events": [
            _event("creates", "confirmed", "unchanged", "Field-service manager required maintenance visibility before Tuesday shift assignment."),
            _event("updates", "confirmed", "minor-semantic", "Rollout lead selected offline mode for the first regional deployment."),
            _event("implements", "confirmed", "unchanged", "Safety coordinator confirmed the dispatch checklist after the Wednesday review."),
            _event("none", "deferred", "unchanged", "Site supervisor asked who confirms the spare part; the depot owner deferred the answer."),
            _event("creates", "confirmed", "unchanged", "Regional support lead confirmed the pilot rollout completed in the first zone."),
            _event("contradicts", "deferred", "major-semantic", "Connectivity reviewer kept the remote-sync risk open because field logs were incomplete."),
            _event("updates", "confirmed", "minor-semantic", "Japanese field liaison confirmed the device power-setting constraint during validation review."),
            _event("none", "deferred", "unchanged", "Maintenance owner postponed the schedule change until the site coordinator responds."),
        ],
        "answers": [
            ("CQ-11", "answerable", ["fact-106-01", "fact-106-02"], ["s12-a-3041", "s12-a-3042"], "complete", "current", False),
            ("CQ-12", "ambiguous", [], ["s12-a-3048"], "not-applicable", "not-applicable", True),
        ],
    },
]


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_scenario(episode: dict[str, Any]) -> dict[str, Any]:
    case_ids = episode["cases"]
    events = []
    for sequence, event_spec in enumerate(episode["events"], start=1):
        event = {
            "eventId": f"event-{sequence:02d}",
            "sequence": sequence,
            "caseId": case_ids[sequence - 1],
            "expectedTemporalEffect": event_spec["expectedTemporalEffect"],
            "expectedReview": {
                "disposition": event_spec["disposition"],
                "correctionClass": event_spec["correctionClass"],
                "rationale": event_spec["rationale"],
            },
        }
        events.append(event)
    checkpoints = []
    for after in (2, 4, 6, 8):
        prefix = case_ids[:after]
        checkpoints.append(
            {
                "afterSequence": after,
                "sourceIds": prefix,
                "candidateIds": [f"candidate-{episode['scenarioId'][-3:]}-{index:02d}" for index in range(1, after + 1)],
                "assertedIds": [f"asserted-{episode['scenarioId'][-3:]}-01"] if after >= 2 else [],
                "inferredExpectations": ["history-preserved"]
                + (["open-review-risk"] if after >= 6 else []),
                "provenanceActivityIds": [f"activity-{episode['scenarioId'][-3:]}-{index:02d}" for index in range(1, after + 1)],
                "contradictionIds": [f"contradiction-{episode['scenarioId'][-3:]}-01"]
                if after >= 6
                else [],
            }
        )
    answers = []
    for answer in episode["answers"]:
        question_id, status, facts, citations, completeness, freshness, abstain = answer
        answers.append(
            {
                "questionId": question_id,
                "status": status,
                "expectedFactIds": facts,
                "expectedCitationIds": citations,
                "completeness": completeness,
                "freshness": freshness,
                "abstain": abstain,
            }
        )
    return {
        "scenarioId": episode["scenarioId"],
        "schemaVersion": "s12.scenario.v1",
        "journeyId": episode["journeyId"],
        "split": episode["split"],
        "events": events,
        "checkpoints": checkpoints,
        "competencyAnswers": answers,
        "sourceManifest": case_ids,
    }


def build_dataset(atomic_path: Path = ATOMIC_PATH) -> tuple[dict[str, Any], dict[str, Any]]:
    atomic = json.loads(atomic_path.read_text(encoding="utf-8"))
    atomic_ids = {case["caseId"] for case in atomic["cases"]}
    scenarios = [build_scenario(episode) for episode in EPISODES]
    for scenario in scenarios:
        if not set(scenario["sourceManifest"]) <= atomic_ids:
            raise ValueError(f"scenario references missing atomic case: {scenario['scenarioId']}")
    dataset = {
        "datasetVersion": "s12.corpus.scenario.v3.deep-pilot",
        "status": "DEEP_PILOT_AUTHORED_PENDING_QA",
        "humanEvidence": False,
        "atomicDatasetVersion": atomic["datasetVersion"],
        "scenarios": scenarios,
    }
    entries = [
        {
            "scenarioId": scenario["scenarioId"],
            "journeyId": scenario["journeyId"],
            "split": scenario["split"],
            "sourceManifest": scenario["sourceManifest"],
            "scenarioDigest": _digest(scenario),
        }
        for scenario in scenarios
    ]
    manifest = {
        "manifestVersion": "s12.corpus.scenario-manifest.v3.deep-pilot",
        "datasetVersion": dataset["datasetVersion"],
        "atomicDatasetVersion": atomic["datasetVersion"],
        "status": "DEEP_PILOT_AUTHORED_PENDING_QA",
        "humanEvidence": False,
        "scenarioCounts": {"development": 4, "validation": 2, "test": 0, "total": 6},
        "scenarios": entries,
        "testPayloadPresent": False,
    }
    manifest["manifestDigest"] = _digest(manifest)
    return dataset, manifest


def write_dataset(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset, manifest = build_dataset(output_dir / "atomic-deep-pilot.v1.json")
    (output_dir / "scenario-deep-pilot.v1.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "scenario-manifest.v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"dataset": dataset["datasetVersion"], **manifest["scenarioCounts"]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_dataset(args.output_dir)


if __name__ == "__main__":
    main()
