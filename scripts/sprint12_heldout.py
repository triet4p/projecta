#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Sprint 12 Phase G held-out custody, review and G6 guards."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypeAlias, cast

JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)
JsonObject: TypeAlias = dict[str, JSONValue]
HELDOUT_VERSION = "s12.heldout.v1"
GAP_CATEGORIES = (
    "released-term-missing",
    "annotation-disagreement",
    "out-of-scope",
    "schema-gap",
    "ontology-change-candidate",
)


class HeldoutError(ValueError):
    """Raised when a held-out evaluation contract is invalid."""


def _object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise HeldoutError(f"{label} must be an object")
    return cast(JsonObject, value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise HeldoutError(f"{label} must be a non-empty string")
    return value


def digest(value: object) -> str:
    """Return a canonical JSON sha256 digest."""

    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def verify_test_custody(
    manifest: Mapping[str, object],
    *,
    expected_atomic: int = 40,
    expected_scenarios: int = 6,
) -> JsonObject:
    """Verify custody status, counts and digest metadata without opening payloads."""

    counts = _object(manifest.get("counts"), "custody.counts")
    failures: list[str] = []
    if manifest.get("manifestVersion") != "s12.corpus.test-custody.v1":
        failures.append("unknown custody manifest version")
    if manifest.get("status") != "CUSTODY_ESTABLISHED":
        failures.append("custody status is not established")
    if manifest.get("payloadPresent") is not True:
        failures.append("test payload is absent from authorized custody boundary")
    if (
        counts.get("atomicCases") != expected_atomic
        or counts.get("scenarios") != expected_scenarios
    ):
        failures.append("custody counts do not match the approved test quota")
    bundle_digest = _string(manifest.get("bundleDigest"), "custody.bundleDigest")
    if not bundle_digest.startswith("sha256:") or len(bundle_digest) != 71:
        failures.append("invalid custody bundle digest")
    return {
        "status": "CUSTODY_VERIFIED" if not failures else "CUSTODY_NOT_ESTABLISHED",
        "failures": failures,
        "payloadPresent": manifest.get("payloadPresent") is True,
        "atomicCases": counts.get("atomicCases"),
        "scenarios": counts.get("scenarios"),
        "bundleDigest": bundle_digest,
    }


def validate_reviewer_protocol(protocol: Mapping[str, object]) -> None:
    """Validate independent target-role and manual-baseline requirements."""

    if int(protocol.get("reviewerCount", 0)) < 3:
        raise HeldoutError("at least three qualified reviewers are required")
    if int(protocol.get("scenarioCount", 0)) < 12:
        raise HeldoutError("at least twelve blinded scenarios are required")
    roles = protocol.get("targetRoles")
    if not isinstance(roles, list) or not roles:
        raise HeldoutError("target roles are required")
    if (
        protocol.get("independentAnnotation") is not True
        or protocol.get("blindedOrder") is not True
    ):
        raise HeldoutError("reviewers must annotate independently in blinded order")
    manual = _object(protocol.get("manualBaseline"), "manualBaseline")
    if (
        manual.get("counterbalanced") is not True
        or manual.get("sameReviewers") is not True
    ):
        raise HeldoutError(
            "manual baseline must be counterbalanced for the same reviewers"
        )


def preregister_run(
    *,
    candidate: Mapping[str, object] | None,
    evaluator_digest: str,
    metrics: Sequence[str],
    thresholds: Mapping[str, object],
    reviewer_protocol: Mapping[str, object],
    abort_conditions: Sequence[str],
    custody: Mapping[str, object],
) -> JsonObject:
    """Prepare the exact held-out plan and block it if candidate/custody is absent."""

    validate_reviewer_protocol(reviewer_protocol)
    if not evaluator_digest.startswith("sha256:"):
        raise HeldoutError("preregistration requires evaluator digest")
    candidate_status = candidate.get("status") if candidate else None
    blocked: list[str] = []
    if candidate_status != "FROZEN":
        blocked.append("no frozen candidate")
    if custody.get("status") != "CUSTODY_VERIFIED":
        blocked.append("test custody is not verified")
    return {
        "preregistrationVersion": HELDOUT_VERSION,
        "status": "PREREGISTERED" if not blocked else "PREREGISTRATION_BLOCKED",
        "candidate": dict(candidate) if candidate else None,
        "evaluatorDigest": evaluator_digest,
        "metrics": list(metrics),
        "thresholds": dict(thresholds),
        "reviewerProtocol": dict(reviewer_protocol),
        "abortConditions": list(abort_conditions),
        "custodyStatus": custody.get("status"),
        "blockers": blocked,
        "heldOutInspected": False,
    }


def execute_blinded_run(
    preregistration: Mapping[str, object],
    *,
    outputs: Mapping[str, object] | None = None,
) -> JsonObject:
    """Execute only after preregistration, custody and frozen-candidate checks pass."""

    if preregistration.get("status") != "PREREGISTERED":
        return {
            "status": "BLINDED_RUN_BLOCKED",
            "reason": "preregistration is blocked",
            "outputCount": 0,
        }
    if outputs is None:
        return {"status": "BLINDED_RUN_MISSING_OUTPUT", "outputCount": 0}
    return {
        "status": "BLINDED_RUN_COMPLETE",
        "outputCount": len(outputs),
        "heldOutInspected": True,
        "rawSensitiveDataIncluded": False,
        "resultDigest": digest(outputs),
    }


def capture_review_records(
    records: Sequence[Mapping[str, object]], *, scenario_count: int
) -> JsonObject:
    """Validate sanitized independent reviewer records without storing raw text."""

    forbidden = {"rawText", "sourceText", "answerText", "comment"}
    if any(forbidden & set(record) for record in records):
        raise HeldoutError("review records contain prohibited raw sensitive data")
    if len(records) < scenario_count * 3:
        return {
            "status": "REVIEW_INCOMPLETE",
            "recordCount": len(records),
            "requiredMinimum": scenario_count * 3,
        }
    return {
        "status": "REVIEW_CAPTURED",
        "recordCount": len(records),
        "scenarioCount": scenario_count,
        "reviewRecordDigest": digest(list(records)),
        "rawSensitiveDataIncluded": False,
    }


def capture_manual_baseline(
    records: Sequence[Mapping[str, object]], *, scenario_count: int
) -> JsonObject:
    """Validate counterbalanced manual-baseline records without raw business text."""

    forbidden = {"rawText", "sourceText", "answerText", "comment"}
    if any(forbidden & set(record) for record in records):
        raise HeldoutError("manual baseline contains prohibited raw sensitive data")
    if len(records) < scenario_count * 3:
        return {
            "status": "MANUAL_BASELINE_INCOMPLETE",
            "recordCount": len(records),
            "requiredMinimum": scenario_count * 3,
        }
    return {
        "status": "MANUAL_BASELINE_CAPTURED",
        "recordCount": len(records),
        "scenarioCount": scenario_count,
        "manualRecordDigest": digest(list(records)),
        "rawSensitiveDataIncluded": False,
    }


def compare_business_utility(
    projecta_records: Sequence[Mapping[str, object]],
    manual_records: Sequence[Mapping[str, object]],
) -> JsonObject:
    """Compare sanitized reviewer utility only when both arms are complete."""

    if not projecta_records or not manual_records:
        return {
            "status": "UTILITY_NOT_AVAILABLE",
            "reason": "both blinded and manual records are required",
        }
    return {
        "status": "UTILITY_SCORED",
        "projectaRecordCount": len(projecta_records),
        "manualRecordCount": len(manual_records),
        "rawSensitiveDataIncluded": False,
    }


def classify_ontology_gap(gap: Mapping[str, object]) -> str:
    """Classify a held-out semantic gap under a finite governed taxonomy."""

    category = _string(gap.get("category"), "gap.category")
    if category not in GAP_CATEGORIES:
        raise HeldoutError(f"unknown ontology-gap category: {category}")
    return category


def verify_evidence_integrity(
    *,
    custody: Mapping[str, object],
    preregistration: Mapping[str, object],
    run: Mapping[str, object],
    reviewer: Mapping[str, object],
    manual: Mapping[str, object],
) -> JsonObject:
    """Verify packet components are present and explicitly report blocked runs."""

    components = {
        "custody": custody,
        "preregistration": preregistration,
        "run": run,
        "reviewer": reviewer,
        "manual": manual,
    }
    missing = [name for name, value in components.items() if not value]
    blocked = [
        name
        for name, value in components.items()
        if str(value.get("status", "")).endswith("BLOCKED")
        or "INCOMPLETE" in str(value.get("status", ""))
    ]
    return {
        "status": "EVIDENCE_VERIFIED"
        if not missing and not blocked
        else "EVIDENCE_BLOCKED",
        "missingComponents": missing,
        "blockedComponents": blocked,
        "componentDigests": {name: digest(value) for name, value in components.items()},
        "omittedCaseCount": 0,
        "rawSensitiveDataIncluded": False,
    }


def build_g6_packet(
    preregistration: Mapping[str, object],
    custody: Mapping[str, object],
    run: Mapping[str, object],
    reviewer: Mapping[str, object],
    manual: Mapping[str, object],
    utility: Mapping[str, object],
    gaps: Sequence[Mapping[str, object]],
    integrity: Mapping[str, object],
) -> JsonObject:
    """Build a G6 packet that cannot claim business quality without held-out evidence."""

    return {
        "packetVersion": "s12.g6.packet.v1",
        "status": "G6_PREPARATION_BLOCKED_CUSTODY_OR_CANDIDATE",
        "preregistration": dict(preregistration),
        "custody": dict(custody),
        "blindedRun": dict(run),
        "reviewerUtility": dict(reviewer),
        "manualBaseline": dict(manual),
        "businessUtility": dict(utility),
        "ontologyGapCount": len(gaps),
        "ontologyGaps": [dict(gap) for gap in gaps],
        "evidenceIntegrity": dict(integrity),
        "heldOutEvidence": False,
        "boundedClaim": None,
        "rawSensitiveDataIncluded": False,
        "businessApproval": "PENDING_HUMAN_APPROVAL",
    }


def write_packet(packet: JsonObject, json_path: Path, markdown_path: Path) -> None:
    """Write G6 JSON and Markdown without held-out payloads."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Sprint 12 G6 Held-out Business Evaluation Packet",
        "",
        f"**Status:** `{packet['status']}`",
        "",
        "The held-out payload remains outside the repository and custody is not established. No business-quality claim is made.",
        "",
        "## Gate state",
        "",
        f"- Preregistration: `{packet['preregistration']['status']}`",
        f"- Custody: `{packet['custody']['status']}`",
        f"- Blinded run: `{packet['blindedRun']['status']}`",
        f"- Reviewer utility: `{packet['reviewerUtility']['status']}`",
        f"- Manual baseline: `{packet['manualBaseline']['status']}`",
        f"- Business utility: `{packet['businessUtility']['status']}`",
        f"- Evidence integrity: `{packet['evidenceIntegrity']['status']}`",
        "- Held-out evidence: `False`",
        "- Bounded claim: `None`",
        "",
        "## Acceptance boundary (S12-93)",
        "",
        "`PENDING_HUMAN_APPROVAL`; approval is not requested for a business-quality claim until custody, frozen candidate, blinded run and reviewer evidence exist.",
        "",
    ]
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Prepare the held-out preregistration and blocked G6 packet."""

    root = Path(__file__).resolve().parents[1]
    custody = json.loads(
        (
            root / "evaluation/sprint-12/corpus/manifests/test-custody.manifest.v1.json"
        ).read_text(encoding="utf-8")
    )
    custody_result = verify_test_custody(custody)
    reviewer_protocol = {
        "reviewerCount": 3,
        "scenarioCount": 12,
        "targetRoles": ["BrSE", "project-manager", "semantic-reviewer"],
        "independentAnnotation": True,
        "blindedOrder": True,
        "manualBaseline": {"counterbalanced": True, "sameReviewers": True},
    }
    preregistration = preregister_run(
        candidate=None,
        evaluator_digest="sha256:e3b25747b7b4d4271b2f043f56704dcc902fef57460cefaa902144651c355f6a",
        metrics=["acceptance", "correction", "review-time", "usefulness", "trust"],
        thresholds={
            "hardInvariants": "no regression",
            "businessUtility": "pre-registered",
        },
        reviewer_protocol=reviewer_protocol,
        abort_conditions=[
            "custody mismatch",
            "candidate digest mismatch",
            "hard-invariant regression",
            "reviewer independence violation",
        ],
        custody=custody_result,
    )
    run = execute_blinded_run(preregistration)
    reviewer = capture_review_records([], scenario_count=12)
    manual = capture_manual_baseline([], scenario_count=12)
    utility = compare_business_utility([], [])
    integrity = verify_evidence_integrity(
        custody=custody_result,
        preregistration=preregistration,
        run=run,
        reviewer=reviewer,
        manual=manual,
    )
    packet = build_g6_packet(
        preregistration, custody_result, run, reviewer, manual, utility, [], integrity
    )
    output_dir = root / "evaluation/sprint-12/heldout"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "preregistration.v1.json").write_text(
        json.dumps(preregistration, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "custody-verification.v1.json").write_text(
        json.dumps(custody_result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "g6-packet.v1.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_packet(
        packet,
        output_dir / "g6-packet.v1.json",
        root / "docs/sprint-plans/sprint-12/g6-business-evaluation.md",
    )
    print(
        json.dumps(
            {
                "status": packet["status"],
                "custody": custody_result["status"],
                "run": run["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
