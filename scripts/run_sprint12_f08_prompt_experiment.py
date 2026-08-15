"""Guarded, single-use Stage A runner for S12-f-08.

The runner is intentionally separate from the closed S12-f-07 runner. It
preflights the approved authorization, frozen execution package, evaluator v2,
prompt artifact, registry/G5 digests, and cache-aware pricing before making any
provider call. It never retries and refuses to overwrite evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import statistics
from pathlib import Path
from typing import Any, Mapping

import sprint12_evaluator as evaluator
from run_sprint12_contract_candidate import run_candidate
from sprint12_pricing import (
    PricingBindingError,
    bind_pricing,
    cost_usd,
    file_digest,
    merged_environment,
)


ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
ATOMIC = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json"
SCENARIO = ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v2.json"
MANIFEST = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"
PREREGISTRATION = OPT / "s12-f-08-relation-prompt-preregistration.v2.json"
AUTHORIZATION = OPT / "s12-f-08-authorization.v2.json"
REGISTRY = OPT / "experiment-registry.v9.json"
G5_PACKET = OPT / "g5-packet.v9.json"
PRICING = OPT / "s12-f-08-pricing-deepseek-v4-flash.v1.json"
PROMPT_ARTIFACT = OPT / "s12-f-08-prompt-v5-composed-relation-contract.v1.txt"
OUTPUT_PATH = OPT / "s12-f-08-relation-prompt-stage-a.v1.json"
RUNS_DIR = OPT / "s12-f-08-relation-prompt-stage-a"

EXPECTED_SCHEDULE = (
    {"pairId": "pair-1", "runNumber": 1, "armOrder": ("control", "candidate")},
    {"pairId": "pair-2", "runNumber": 2, "armOrder": ("candidate", "control")},
    {"pairId": "pair-3", "runNumber": 3, "armOrder": ("control", "candidate")},
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_output(*args: str) -> str:
    return subprocess.check_output(("git", *args), cwd=ROOT, text=True).strip()


def commit_is_ancestor(commit_sha: str) -> bool:
    try:
        subprocess.run(
            ("git", "merge-base", "--is-ancestor", commit_sha, "HEAD"),
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def execution_package_digests() -> dict[str, str]:
    return {
        "evaluatorCode": file_digest(ROOT / "scripts/sprint12_evaluator.py"),
        "runnerCode": file_digest(Path(__file__)),
        "pricingModuleCode": file_digest(ROOT / "scripts/sprint12_pricing.py"),
        "promptImplementation": file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/prompt.py"
        ),
        "promptArtifact": file_digest(PROMPT_ARTIFACT),
        "runtimeContractCode": file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/contracts.py"
        ),
        "runtimeServiceCode": file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/service.py"
        ),
        "pricingArtifact": file_digest(PRICING),
        "datasetManifest": file_digest(MANIFEST),
    }


def _load_runtime_environment() -> None:
    for key, value in merged_environment().items():
        os.environ.setdefault(key, value)


def _normalized_schedule(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        {
            "pairId": item.get("pairId"),
            "runNumber": item.get("runNumber"),
            "armOrder": tuple(item.get("armOrder", ())),
        }
        for item in value
        if isinstance(item, dict)
    )


def _case_profile(case_ids: tuple[str, ...]) -> dict[str, int]:
    atomic = {case["caseId"]: case for case in load(ATOMIC)["cases"]}
    manifest = {item["caseId"]: item for item in load(MANIFEST)["atomicCases"]}
    selected = [atomic[case_id] for case_id in case_ids]
    return {
        "positiveRelationCases": sum(bool(case["gold"]["relations"]) for case in selected),
        "hardNegativeOrSemanticGapCases": sum(
            bool(case["gold"]["semanticGaps"]) for case in selected
        ),
        "safetyAbstentionOrIsolationCases": sum(
            case["gold"]["abstention"]["required"] is True
            and manifest[case["caseId"]]["slice"]
            in {
                "explicit-ambiguity-or-abstention",
                "cross-project-isolation",
                "fabricated-link",
            }
            for case in selected
        ),
        "additionalTemporalControlCases": sum(
            manifest[case["caseId"]]["slice"] == "temporal-change"
            for case in selected
        ),
    }


def preflight() -> tuple[dict[str, Any], tuple[str, ...], dict[str, object]]:
    _load_runtime_environment()
    prereg = load(PREREGISTRATION)
    authorization = load(AUTHORIZATION)
    registry = load(REGISTRY)
    g5 = load(G5_PACKET)
    if prereg.get("status") != "PREREGISTERED_NOT_EXECUTED":
        raise SystemExit("S12-f-08 preregistration is not immutable/not-executed")
    if authorization.get("status") != "APPROVED_FOR_DEVELOPMENT_STAGE_A":
        raise SystemExit("S12-f-08 Stage A is not authorized")
    if registry.get("registryVersion") != "s12.experiment-registry.v9":
        raise SystemExit("S12-f-08 requires registry v9")
    if g5.get("packetVersion") != "s12.g5.packet.v9":
        raise SystemExit("S12-f-08 requires G5 packet v9")
    if registry.get("status") != "G5_DEVELOPMENT_STAGE_A_AUTHORIZED_S12_F08":
        raise SystemExit("registry does not authorize S12-f-08 Stage A")
    if g5.get("status") != registry.get("status"):
        raise SystemExit("G5 status does not match registry authorization")
    if file_digest(PREREGISTRATION) != authorization["preregistration"]["digest"]:
        raise SystemExit("authorization does not bind the f08 preregistration digest")
    if authorization["registry"].get("digest") != registry.get("registryDigest"):
        raise SystemExit("authorization does not bind the registry canonical digest")
    if authorization["registry"].get("fileDigest") != file_digest(REGISTRY):
        raise SystemExit("authorization does not bind the registry file digest")
    if g5.get("registryDigest") != registry.get("registryDigest"):
        raise SystemExit("G5 does not bind the registry canonical digest")
    if g5.get("pendingExperiment", {}).get("authorizationDigest") != file_digest(
        AUTHORIZATION
    ):
        raise SystemExit("G5 does not bind the authorization digest")
    package = authorization.get("executionPackage")
    if not isinstance(package, dict):
        raise SystemExit("authorization is missing the frozen execution package")
    if not isinstance(package.get("commitSha"), str) or not commit_is_ancestor(
        package["commitSha"]
    ):
        raise SystemExit("execution package commit SHA is not an ancestor of HEAD")
    if package.get("digests") != execution_package_digests():
        raise SystemExit("execution package digests do not match the working tree")
    if prereg.get("promptArtifact", {}).get("digest") != file_digest(PROMPT_ARTIFACT):
        raise SystemExit("prompt artifact digest mismatch")
    if prereg.get("pricingContract", {}).get("artifactDigest") != file_digest(PRICING):
        raise SystemExit("pricing artifact digest mismatch")
    try:
        pricing = bind_pricing(
            PRICING,
            os.environ,
            expected_model=str(prereg["candidate"]["configuration"]["model"]),
        )
    except PricingBindingError as error:
        raise SystemExit(str(error)) from error
    case_ids = tuple(str(case_id) for case_id in prereg["stageA"]["caseIds"])
    if len(case_ids) != 16 or len(set(case_ids)) != 16:
        raise SystemExit("S12-f-08 Stage A must contain exactly 16 unique cases")
    selected = [case for case in load(ATOMIC)["cases"] if case["caseId"] in case_ids]
    if len(selected) != len(case_ids) or any(
        case["split"] != "development" for case in selected
    ):
        raise SystemExit("S12-f-08 case set must remain development-only")
    if _case_profile(case_ids) != prereg["stageA"]["selectionProfile"]:
        raise SystemExit("S12-f-08 selection profile does not match manifest/gold")
    if _normalized_schedule(prereg["stageA"].get("temporalPairing", {}).get("schedule")) != EXPECTED_SCHEDULE:
        raise SystemExit("S12-f-08 temporal pairing schedule is not fixed/interleaved")
    return prereg, case_ids, pricing


def _case_metric(case: Mapping[str, Any], name: str) -> float:
    if case.get("status") != "scored":
        return 0.0
    if name in {"abstentionAccuracy", "hallucinationRate"}:
        return float(case.get(name, 0.0))
    field = {"entityMacroF1": "entities", "relationMacroF1": "relations"}.get(
        name, name
    )
    metric = case.get(field, {})
    return float(metric.get("f1", 0.0)) if isinstance(metric, dict) else 0.0


def primary_metrics(runs: list[dict[str, Any]]) -> dict[str, float]:
    values = {
        name: []
        for name in (
            "entityMacroF1",
            "relationMacroF1",
            "abstentionAccuracy",
            "hallucinationRate",
        )
    }
    positive: list[float] = []
    true_positive = gold = predicted = 0
    for run in runs:
        for case in run["perCase"].values():
            for name in values:
                values[name].append(_case_metric(case, name))
            relation = case.get("relations", {})
            if isinstance(relation, dict) and int(relation.get("gold", 0)) > 0:
                positive.append(float(relation.get("f1", 0.0)))
                true_positive += int(relation.get("truePositive", 0))
                gold += int(relation.get("gold", 0))
                predicted += int(relation.get("predicted", 0))
    result = {
        name: statistics.fmean(items) if items else 0.0
        for name, items in values.items()
    }
    result["positiveRelationCaseRuns"] = len(positive)
    result["positiveRelationMacroF1"] = statistics.fmean(positive) if positive else 0.0
    result["positiveRelationMicroF1"] = (
        2 * true_positive / (gold + predicted) if gold + predicted else 1.0
    )
    return result


def sensitivity_metrics(
    control: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> dict[str, float]:
    names = (
        "entityMacroF1",
        "relationMacroF1",
        "abstentionAccuracy",
        "hallucinationRate",
    )
    values = {name: [] for name in names}
    for control_run, candidate_run in zip(control, candidate, strict=True):
        common = set(control_run["perCase"]) & set(candidate_run["perCase"])
        common = {
            case_id
            for case_id in common
            if control_run["perCase"][case_id].get("status") == "scored"
            and candidate_run["perCase"][case_id].get("status") == "scored"
        }
        for case_id in common:
            for name in names:
                values[name].append(
                    _case_metric(candidate_run["perCase"][case_id], name)
                    - _case_metric(control_run["perCase"][case_id], name)
                )
    return {name: statistics.fmean(items) if items else 0.0 for name, items in values.items()}


def arm_hard_gate(runs: list[dict[str, Any]]) -> bool:
    return all(
        not run["failureCounts"] and int(run["missingOutputCount"]) == 0
        for run in runs
    )


def _supersession_case_ids(case_ids: tuple[str, ...]) -> set[str]:
    slices = {
        item["caseId"]: item.get("slice") for item in load(MANIFEST)["atomicCases"]
    }
    return {
        case_id for case_id in case_ids if slices.get(case_id) == "contradiction-or-supersession"
    }


def supersession_false_positives(
    runs: list[dict[str, Any]], case_ids: tuple[str, ...]
) -> int:
    target = _supersession_case_ids(case_ids)
    return sum(
        1
        for run in runs
        for case_id in target
        if run["perCase"].get(case_id, {}).get("status") == "scored"
        and float(run["perCase"][case_id].get("abstentionAccuracy", 1.0)) == 0.0
    )


def write_report(
    path: Path, report: dict[str, Any], pricing: dict[str, object]
) -> dict[str, Any]:
    if path.exists():
        raise SystemExit(f"refusing to overwrite run report: {path}")
    records = report.get("operationalRecords", [])
    if not isinstance(records, list):
        raise SystemExit("report is missing operational records")
    for record in records:
        if not isinstance(record, dict):
            raise SystemExit("malformed operational record")
        record["costUsd"] = cost_usd(record, pricing)
    report["operational"] = evaluator.score_operational(records)
    report["operational"]["pricing"] = {
        "status": "BOUND",
        "artifactDigest": pricing["artifactDigest"],
        "currency": pricing["currency"],
        "unit": pricing["unit"],
        "sourceUrl": pricing["sourceUrl"],
        "retrievedAt": pricing["retrievedAt"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "reportPath": (
            path.relative_to(ROOT).as_posix()
            if path.is_relative_to(ROOT)
            else path.as_posix()
        ),
        "reportDigest": file_digest(path),
        "runId": path.stem.removesuffix(".report.v1"),
        "status": report["status"],
        "failureCount": report["failureCount"],
        "missingOutputCount": report["missingOutputCount"],
        "failureCounts": report["operational"]["failureCounts"],
        "usage": report["operational"]["usage"],
        "costUsd": report["operational"]["costUsd"],
        "metrics": {
            name: report["metrics"][name]
            for name in (
                "entityMacroF1",
                "relationMacroF1",
                "abstentionAccuracy",
                "hallucinationRate",
                "linkMacroF1",
            )
        },
        "configuration": report["configuration"],
        "digests": report["digests"],
        "perCase": report["metrics"]["perCase"],
    }


def execute_stage_a(
    prereg: dict[str, Any],
    case_ids: tuple[str, ...],
    pricing: dict[str, object],
    *,
    runner=run_candidate,
    report_dir: Path = RUNS_DIR,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    variants: dict[str, list[dict[str, Any]]] = {"control": [], "candidate": []}
    trace: list[dict[str, Any]] = []
    model = str(prereg["candidate"]["configuration"]["model"])
    prompt_by_variant = {
        "control": prereg["control"]["configuration"]["promptVersion"],
        "candidate": prereg["candidate"]["configuration"]["promptVersion"],
    }
    for pair in EXPECTED_SCHEDULE:
        for arm_position, variant in enumerate(pair["armOrder"], start=1):
            path = report_dir / f"{pair['pairId']}-{arm_position:02d}-{variant}.report.v1.json"
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
                candidate_kind=f"s12-f-08-{variant}-relation-prompt",
            )
            summary = write_report(path, report, pricing)
            summary.update(
                {
                    "pairId": pair["pairId"],
                    "runNumber": pair["runNumber"],
                    "armOrder": list(pair["armOrder"]),
                    "armPosition": arm_position,
                }
            )
            variants[variant].append(summary)
            trace.append(
                {
                    "sequence": len(trace) + 1,
                    "pairId": pair["pairId"],
                    "runNumber": pair["runNumber"],
                    "arm": variant,
                    "armPosition": arm_position,
                    "reportPath": summary["reportPath"],
                }
            )
    return variants, trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if OUTPUT_PATH.exists():
        raise SystemExit(f"refusing to overwrite Stage A artifact: {OUTPUT_PATH}")
    prereg, case_ids, pricing = preflight()
    variants, trace = execute_stage_a(prereg, case_ids, pricing)
    control_primary = primary_metrics(variants["control"])
    candidate_primary = primary_metrics(variants["candidate"])
    primary_deltas = {
        "entityMacroF1": candidate_primary["entityMacroF1"] - control_primary["entityMacroF1"],
        "relationMacroF1": candidate_primary["relationMacroF1"] - control_primary["relationMacroF1"],
        "abstentionAccuracy": candidate_primary["abstentionAccuracy"] - control_primary["abstentionAccuracy"],
        "hallucinationRateReduction": control_primary["hallucinationRate"] - candidate_primary["hallucinationRate"],
        "positiveRelationMacroF1": candidate_primary["positiveRelationMacroF1"] - control_primary["positiveRelationMacroF1"],
        "positiveRelationMicroF1": candidate_primary["positiveRelationMicroF1"] - control_primary["positiveRelationMicroF1"],
    }
    sensitivity = sensitivity_metrics(variants["control"], variants["candidate"])
    candidate_hard = arm_hard_gate(variants["candidate"])
    control_hard = arm_hard_gate(variants["control"])
    false_positives = supersession_false_positives(variants["candidate"], case_ids)
    gates = {
        "candidateHardGate": candidate_hard,
        "controlHardGate": control_hard,
        "primaryRelationMacroF1": primary_deltas["relationMacroF1"] >= 0.05,
        "sensitivityRelationMacroF1": sensitivity["relationMacroF1"] >= 0.0,
        "positiveRelationMacroF1Minimum": candidate_primary["positiveRelationMacroF1"] >= 0.05,
        "positiveRelationMacroF1Delta": primary_deltas["positiveRelationMacroF1"] >= 0.05,
        "positiveRelationMicroF1Minimum": candidate_primary["positiveRelationMicroF1"] >= 0.05,
        "entityMacroF1NonInferiority": primary_deltas["entityMacroF1"] >= -0.01,
        "abstentionNonInferiority": primary_deltas["abstentionAccuracy"] >= -0.01,
        "hallucinationNonIncrease": primary_deltas["hallucinationRateReduction"] >= 0.0,
        "supersessionFalsePositiveZero": false_positives == 0,
    }
    stage_a_pass = all(gates.values())
    output = {
        "artifactVersion": "s12.s12-f-08.relation-prompt-stage-a.v1",
        "experimentId": "s12-f-08",
        "status": "STAGE_A_COMPLETED",
        "decision": "STAGE_A_ELIGIBLE_FOR_STAGE_B" if stage_a_pass else "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B",
        "stageATechnicalPass": stage_a_pass,
        "stageBAuthorized": False,
        "caseCount": len(case_ids),
        "executionCount": len(trace) * len(case_ids),
        "caseIds": list(case_ids),
        "invocationTrace": trace,
        "control": {
            "primaryMetrics": control_primary,
            "hardGatesPass": control_hard,
            "runs": variants["control"],
        },
        "candidate": {
            "primaryMetrics": candidate_primary,
            "hardGatesPass": candidate_hard,
            "supersessionFalsePositiveCount": false_positives,
            "runs": variants["candidate"],
        },
        "deltas": {
            "primary": primary_deltas,
            "sensitivity": sensitivity,
        },
        "gates": gates,
        "accounting": {
            "costAccountingStatus": "BOUND",
            "pricingArtifactDigest": pricing["artifactDigest"],
            "usageRequired": True,
            "latencyRequired": True,
        },
        "digests": execution_package_digests(),
        "heldOutInspected": False,
        "rawSensitiveDataIncluded": False,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
