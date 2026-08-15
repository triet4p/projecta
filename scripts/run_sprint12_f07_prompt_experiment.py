"""Guarded S12-f-07 Stage A runner.

The runner is deliberately authorization-gated.  Importing it or running its
preflight performs no provider call; Stage A starts only after a separate
approved authorization artifact is written.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
from pathlib import Path
from typing import Any

from run_sprint12_contract_candidate import run_candidate


ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
PREREGISTRATION = OPT / "s12-f-07-relation-prompt-preregistration.v2.json"
AUTHORIZATION = OPT / "s12-f-07-authorization.v2.json"
REGISTRY = OPT / "experiment-registry.v7.json"
RUNS_DIR = OPT / "s12-f-07-relation-prompt-stage-a"
OUTPUT_PATH = OPT / "s12-f-07-relation-prompt-stage-a.v1.json"
ATOMIC = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json"
SCENARIO = ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v2.json"
MANIFEST = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"
G5_PACKET = OPT / "g5-packet.v7.json"

EXPECTED_PAIR_SCHEDULE = (
    {"pairId": "pair-1", "runNumber": 1, "armOrder": ("control", "candidate")},
    {"pairId": "pair-2", "runNumber": 2, "armOrder": ("candidate", "control")},
    {"pairId": "pair-3", "runNumber": 3, "armOrder": ("control", "candidate")},
)


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def current_commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_is_ancestor(commit_sha: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
        cwd=ROOT,
        check=False,
    ).returncode == 0


def execution_package_digests() -> dict[str, str]:
    return {
        "promptArtifact": file_digest(
            OPT / "s12-f-07-prompt-v4-relation-decision-rubric.v1.txt"
        ),
        "promptImplementation": file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/prompt.py"
        ),
        "stageRunnerCode": file_digest(Path(__file__)),
        "candidateRunnerCode": file_digest(
            ROOT / "scripts/run_sprint12_contract_candidate.py"
        ),
        "evaluatorCode": file_digest(ROOT / "scripts/sprint12_evaluator.py"),
    }


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_profile(case_ids: tuple[str, ...]) -> dict[str, int]:
    atomic = {case["caseId"]: case for case in load(ATOMIC)["cases"]}
    manifest = {item["caseId"]: item for item in load(MANIFEST)["atomicCases"]}
    selected = [atomic[case_id] for case_id in case_ids]
    positive_relation = sum(bool(case["gold"]["relations"]) for case in selected)
    hard_negative = sum(
        bool(case["gold"]["semanticGaps"])
        for case in selected
    )
    safety = sum(
        case["gold"]["abstention"]["required"] is True
        and manifest[case["caseId"]]["slice"] in {
            "explicit-ambiguity-or-abstention",
            "cross-project-isolation",
            "fabricated-link",
        }
        for case in selected
    )
    temporal = sum(manifest[case["caseId"]]["slice"] == "temporal-change" for case in selected)
    return {
        "positiveRelationCases": positive_relation,
        "hardNegativeOrSemanticGapCases": hard_negative,
        "safetyAbstentionOrIsolationCases": safety,
        "additionalTemporalControlCases": temporal,
    }


def preflight() -> tuple[dict[str, Any], tuple[str, ...]]:
    prereg = load(PREREGISTRATION)
    authorization = load(AUTHORIZATION)
    registry = load(REGISTRY)
    if prereg["status"] != "PREREGISTERED_NOT_EXECUTED":
        raise SystemExit("S12-f-07 preregistration is not immutable/not-executed")
    if prereg["executionAuthorized"] is not False:
        raise SystemExit("S12-f-07 preregistration must remain executionUnauthorized")
    if authorization["status"] != "APPROVED_FOR_DEVELOPMENT_STAGE_A":
        raise SystemExit("S12-f-07 Stage A is not authorized")
    g5 = load(G5_PACKET)
    if file_digest(PREREGISTRATION) != authorization["preregistration"]["digest"]:
        raise SystemExit("authorization does not bind the S12-f-07 preregistration digest")
    if authorization["registry"]["digest"] != registry.get("registryDigest"):
        raise SystemExit("authorization does not bind the current registry digest")
    if g5["registryDigest"] != registry.get("registryDigest"):
        raise SystemExit("G5 does not bind the current registry digest")
    if g5["pendingExperiment"]["authorizationDigest"] != file_digest(AUTHORIZATION):
        raise SystemExit("G5 does not bind the current authorization digest")
    if g5["pendingExperiment"]["preregistrationDigest"] != file_digest(PREREGISTRATION):
        raise SystemExit("G5 does not bind the current preregistration digest")
    package = authorization.get("executionPackage")
    if not isinstance(package, dict):
        raise SystemExit("authorization is missing the frozen execution package")
    if not isinstance(package.get("commitSha"), str) or not commit_is_ancestor(
        package["commitSha"]
    ):
        raise SystemExit("execution package commit SHA is not an ancestor of HEAD")
    if package.get("digests") != execution_package_digests():
        raise SystemExit("execution package code digests do not match the working tree")
    if registry["registryVersion"] != "s12.experiment-registry.v7":
        raise SystemExit("S12-f-07 requires registry v7")
    if g5.get("packetVersion") != "s12.g5.packet.v7":
        raise SystemExit("S12-f-07 requires G5 packet v7")
    registered = next(item for item in registry["experiments"] if item["experimentId"] == "s12-f-07")
    if registered["status"] not in {"REGISTERED", "REGISTERED_PENDING_AUTHORIZATION"}:
        raise SystemExit("S12-f-07 registry record is not registered")
    if registered["preregistration"]["digest"] != file_digest(PREREGISTRATION):
        raise SystemExit("registry does not bind the S12-f-07 preregistration digest")
    prompt_artifact = ROOT / "evaluation/sprint-12/optimization/s12-f-07-prompt-v4-relation-decision-rubric.v1.txt"
    if file_digest(prompt_artifact) != prereg["promptArtifact"]["digest"]:
        raise SystemExit("prompt artifact digest mismatch")
    case_ids = tuple(str(case_id) for case_id in prereg["stageA"]["caseIds"])
    if len(case_ids) != 16 or len(set(case_ids)) != 16:
        raise SystemExit("S12-f-07 Stage A must contain exactly 16 unique cases")
    atomic = {case["caseId"]: case for case in load(ATOMIC)["cases"]}
    if any(case_id not in atomic for case_id in case_ids):
        raise SystemExit("S12-f-07 case set contains an unknown case")
    if any(atomic[case_id]["split"] != "development" for case_id in case_ids):
        raise SystemExit("S12-f-07 case set must remain development-only")
    if _case_profile(case_ids) != prereg["stageA"]["selectionProfile"]:
        raise SystemExit("S12-f-07 selection profile does not match manifest/gold")
    if prereg["candidate"]["configuration"]["promptVersion"] != "m3.prompt.v4.relation-decision-rubric":
        raise SystemExit("S12-f-07 candidate prompt is not v4")
    schedule = prereg["stageA"].get("temporalPairing", {}).get("schedule")
    normalized_schedule = tuple(
        {
            "pairId": item.get("pairId"),
            "runNumber": item.get("runNumber"),
            "armOrder": tuple(item.get("armOrder", ())),
        }
        for item in schedule or ()
    )
    if normalized_schedule != EXPECTED_PAIR_SCHEDULE:
        raise SystemExit("S12-f-07 temporal pairing schedule is not fixed and interleaved")
    return prereg, case_ids


def write_report(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        raise SystemExit(f"refusing to overwrite run report: {path}")
    input_price = os.environ.get("PROJECTA_LLM_PRICE_INPUT_USD_PER_1M")
    output_price = os.environ.get("PROJECTA_LLM_PRICE_OUTPUT_USD_PER_1M")
    if input_price is not None and output_price is not None:
        usage = report["operational"]["usage"]
        report["operational"]["costUsd"] = (
            int(usage["inputTokens"]) * float(input_price)
            + int(usage["outputTokens"]) * float(output_price)
        ) / 1_000_000
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = (
        path.relative_to(ROOT).as_posix()
        if path.is_relative_to(ROOT)
        else path.as_posix()
    )
    return {
        "reportPath": report_path,
        "reportDigest": file_digest(path),
        "runId": path.stem.removesuffix(".report.v1"),
        "status": report["status"],
        "failureCount": report["failureCount"],
        "missingOutputCount": report["missingOutputCount"],
        "failureCounts": report["operational"]["failureCounts"],
        "usage": report["operational"]["usage"],
        "costUsd": report["operational"].get("costUsd"),
        "metrics": {name: report["metrics"][name] for name in (
            "entityMacroF1", "relationMacroF1", "abstentionAccuracy", "hallucinationRate", "linkMacroF1"
        )},
        "configuration": report["configuration"],
        "digests": report["digests"],
        "perCase": report["metrics"]["perCase"],
    }


def _case_metric(case: dict[str, Any], name: str) -> float:
    if case.get("status") != "scored":
        return 0.0
    if name in {"abstentionAccuracy", "hallucinationRate"}:
        return float(case.get(name, 0.0))
    return float(case.get(name, {}).get("f1", 0.0))


def primary_metrics(runs: list[dict[str, Any]]) -> dict[str, float]:
    values: dict[str, list[float]] = {name: [] for name in (
        "entityMacroF1", "relationMacroF1", "abstentionAccuracy", "hallucinationRate"
    )}
    for run in runs:
        for case in run["perCase"].values():
            for name in values:
                values[name].append(_case_metric(case, name))
    return {name: statistics.fmean(items) if items else 0.0 for name, items in values.items()}


def sensitivity_metrics(control: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, float]:
    values: dict[str, list[float]] = {name: [] for name in (
        "entityMacroF1", "relationMacroF1", "abstentionAccuracy", "hallucinationRate"
    )}
    for control_run, candidate_run in zip(control, candidate, strict=True):
        common = set(control_run["perCase"]) & set(candidate_run["perCase"])
        common = {
            case_id for case_id in common
            if control_run["perCase"][case_id].get("status") == "scored"
            and candidate_run["perCase"][case_id].get("status") == "scored"
        }
        for case_id in common:
            for name in values:
                values[name].append(
                    (_case_metric(control_run["perCase"][case_id], name),
                     _case_metric(candidate_run["perCase"][case_id], name))
                )
    result = {}
    for name, pairs in values.items():
        result[name] = statistics.fmean(candidate - control for control, candidate in pairs) if pairs else 0.0
    return result


def arm_hard_gate(runs: list[dict[str, Any]]) -> bool:
    return all(
        not run["failureCounts"] and int(run["missingOutputCount"]) == 0
        for run in runs
    )


def price_reports(runs: list[dict[str, Any]]) -> str:
    input_price = os.environ.get("PROJECTA_LLM_PRICE_INPUT_USD_PER_1M")
    output_price = os.environ.get("PROJECTA_LLM_PRICE_OUTPUT_USD_PER_1M")
    if input_price is None or output_price is None:
        return "NOT_BOUND_PRESELECTION"
    if any(run.get("costUsd") is None for run in runs):
        return "INCOMPLETE"
    return "AVAILABLE"


def execute_stage_a(
    prereg: dict[str, Any],
    case_ids: tuple[str, ...],
    *,
    runner=run_candidate,
    report_dir: Path = RUNS_DIR,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Execute the fixed six-invocation interleaved schedule exactly once."""

    variants: dict[str, list[dict[str, Any]]] = {"control": [], "candidate": []}
    invocation_trace: list[dict[str, Any]] = []
    model = str(prereg["candidate"]["configuration"]["model"])
    prompt_by_variant = {
        "control": prereg["control"]["configuration"]["promptVersion"],
        "candidate": prereg["candidate"]["configuration"]["promptVersion"],
    }
    for pair in EXPECTED_PAIR_SCHEDULE:
        for arm_position, variant in enumerate(pair["armOrder"], start=1):
            path = report_dir / (
                f"{pair['pairId']}-{arm_position:02d}-{variant}.report.v1.json"
            )
            if path.exists():
                raise SystemExit(f"refusing to overwrite run report: {path}")
            os.environ["PROJECTA_LLM_MODEL"] = model
            report = runner(
                atomic_path=ATOMIC,
                scenario_path=SCENARIO,
                manifest_path=MANIFEST,
                prompt_variant=prompt_by_variant[variant],
                case_ids=case_ids,
                sampling_configuration=None,
                candidate_kind=f"s12-f-07-{variant}-relation-prompt",
            )
            summary = write_report(path, report)
            summary.update(
                {
                    "pairId": pair["pairId"],
                    "runNumber": pair["runNumber"],
                    "armOrder": list(pair["armOrder"]),
                    "armPosition": arm_position,
                }
            )
            variants[variant].append(summary)
            invocation_trace.append(
                {
                    "sequence": len(invocation_trace) + 1,
                    "pairId": pair["pairId"],
                    "runNumber": pair["runNumber"],
                    "arm": variant,
                    "armPosition": arm_position,
                    "reportPath": summary["reportPath"],
                }
            )
    return variants, invocation_trace


def main() -> None:
    if OUTPUT_PATH.exists():
        raise SystemExit(f"refusing to overwrite Stage A artifact: {OUTPUT_PATH}")
    prereg, case_ids = preflight()
    variants, invocation_trace = execute_stage_a(prereg, case_ids)
    price_status = price_reports(variants["control"] + variants["candidate"])
    control_primary = primary_metrics(variants["control"])
    candidate_primary = primary_metrics(variants["candidate"])
    primary_deltas = {
        "entityMacroF1": candidate_primary["entityMacroF1"] - control_primary["entityMacroF1"],
        "relationMacroF1": candidate_primary["relationMacroF1"] - control_primary["relationMacroF1"],
        "abstentionAccuracy": candidate_primary["abstentionAccuracy"] - control_primary["abstentionAccuracy"],
        "hallucinationRateReduction": control_primary["hallucinationRate"] - candidate_primary["hallucinationRate"],
    }
    sensitivity_deltas = sensitivity_metrics(variants["control"], variants["candidate"])
    candidate_hard = arm_hard_gate(variants["candidate"])
    control_hard = arm_hard_gate(variants["control"])
    comparison_integrity = "CLEAN" if control_hard else "DEGRADED_CONTROL_FAILURE"
    semantic_gates = {
        "primaryRelationMacroF1": primary_deltas["relationMacroF1"] >= 0.05,
        "sensitivityRelationMacroF1": sensitivity_deltas["relationMacroF1"] >= 0.0,
        "primaryEntityMacroF1": primary_deltas["entityMacroF1"] >= -0.01,
        "primaryAbstentionAccuracy": primary_deltas["abstentionAccuracy"] >= -0.01,
        "primaryHallucinationRate": primary_deltas["hallucinationRateReduction"] >= 0.0,
    }
    semantic_pass = all(semantic_gates.values())
    stage_a_technical_pass = candidate_hard and control_hard and semantic_pass
    stage_b = stage_a_technical_pass and price_status == "AVAILABLE"
    if not stage_a_technical_pass:
        decision = "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
    elif price_status != "AVAILABLE":
        decision = "STAGE_A_TECHNICAL_PASS_PENDING_PRICING"
    else:
        decision = "STAGE_A_PASS"
    artifact = {
        "artifactVersion": "s12.s12-f-07.relation-prompt-stage-a.v1",
        "status": "STAGE_A_COMPLETED",
        "experimentId": "s12-f-07",
        "datasetVersion": prereg["fixedArtifacts"]["datasetVersion"],
        "datasetManifestDigest": prereg["fixedArtifacts"]["datasetManifestDigest"],
        "authorizationDigest": file_digest(AUTHORIZATION),
        "preregistrationDigest": file_digest(PREREGISTRATION),
        "protocol": prereg["stageA"],
        "temporalPairing": {
            "strategy": "interleaved_paired_runs",
            "schedule": [
                {
                    "pairId": pair["pairId"],
                    "runNumber": pair["runNumber"],
                    "armOrder": list(pair["armOrder"]),
                }
                for pair in EXPECTED_PAIR_SCHEDULE
            ],
            "invocationTrace": invocation_trace,
        },
        "denominatorContract": prereg["denominatorContract"],
        "control": {"hardGatesPass": control_hard, "runs": variants["control"]},
        "candidate": {"hardGatesPass": candidate_hard, "runs": variants["candidate"]},
        "comparison": {
            "primary": {"metrics": {"control": control_primary, "candidate": candidate_primary}, "deltas": primary_deltas},
            "sensitivityCommonValid": {"deltas": sensitivity_deltas},
            "semanticGates": semantic_gates,
            "semanticGatesPass": semantic_pass,
            "comparisonIntegrity": comparison_integrity,
        },
        "accounting": {
            "latencyPresent": True,
            "usagePresent": True,
            "costAccountingStatus": price_status,
            "selectionBlockedUntilPricingBound": price_status != "AVAILABLE",
        },
        "hardGates": {
            "candidate": "PASS" if candidate_hard else "FAIL",
            "control": "PASS" if control_hard else "FAIL",
        },
        "stageBAuthorized": stage_b,
        "stageATechnicalPass": stage_a_technical_pass,
        "decision": decision,
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "digests": execution_package_digests(),
    }
    OUTPUT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": artifact["status"], "decision": artifact["decision"], "stageBAuthorized": stage_b}, sort_keys=True))


if __name__ == "__main__":
    main()
