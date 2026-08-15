#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Execute S12-77 Stage A as paired control/candidate model runs."""

from __future__ import annotations

import hashlib
import json
import os
import statistics
from pathlib import Path

from run_sprint12_contract_candidate import run_candidate

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
PREREG_PATH = OPTIMIZATION / "s12-77-model-preregistration.v2.json"
ATOMIC_PATH = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json"
SCENARIO_PATH = ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v2.json"
MANIFEST_PATH = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"
RUNS_DIR = OPTIMIZATION / "s12-77-model-stage-a"
OUTPUT_PATH = OPTIMIZATION / "s12-77-model-stage-a.v1.json"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


def write_report(path: Path, report: dict[str, object]) -> dict[str, object]:
    if path.exists():
        raise SystemExit(f"refusing to overwrite existing run report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "reportPath": str(path.relative_to(ROOT)).replace("\\", "/"),
        "reportDigest": file_digest(path),
        "runId": path.stem.removesuffix(".report.v1"),
        "status": report["status"],
        "failureCount": report["failureCount"],
        "missingOutputCount": report["missingOutputCount"],
        "failureCounts": report["operational"]["failureCounts"],
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
    }


def aggregate(runs: list[dict[str, object]], model: str) -> dict[str, object]:
    failure_counts: dict[str, int] = {}
    for run in runs:
        for name, count in run["failureCounts"].items():
            failure_counts[name] = failure_counts.get(name, 0) + int(count)
    metric_names = (
        "entityMacroF1",
        "relationMacroF1",
        "abstentionAccuracy",
        "hallucinationRate",
        "linkMacroF1",
    )
    metrics = {
        name: statistics.fmean(float(run["metrics"][name]) for run in runs)
        for name in metric_names
    }
    return {
        "model": model,
        "independentRunCount": len(runs),
        "runs": runs,
        "aggregateFailureCounts": failure_counts,
        "aggregateMissingOutputCount": sum(int(run["missingOutputCount"]) for run in runs),
        "meanMetrics": metrics,
        "hardGatesPass": not failure_counts and not any(
            int(run["missingOutputCount"]) for run in runs
        ),
    }


def main() -> None:
    if OUTPUT_PATH.exists():
        raise SystemExit(f"refusing to overwrite existing Stage A artifact: {OUTPUT_PATH}")
    load_dotenv()
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if prereg.get("status") != "AUTHORIZED_NOT_EXECUTED" or not prereg.get(
        "executionAuthorized"
    ):
        raise SystemExit("S12-77 preregistration is not execution-authorized")
    control_model = str(prereg["controlModel"])
    candidate_model = str(prereg["candidateModel"])
    case_ids = tuple(str(case_id) for case_id in prereg["stageA"]["caseIds"])
    if len(case_ids) != 16:
        raise SystemExit("Stage A must contain exactly 16 cases")
    if control_model == candidate_model:
        raise SystemExit("control and candidate models must differ")

    variants: dict[str, list[dict[str, object]]] = {"control": [], "candidate": []}
    for variant, model in (("control", control_model), ("candidate", candidate_model)):
        for run_number in range(1, 4):
            os.environ["PROJECTA_LLM_MODEL"] = model
            report = run_candidate(
                atomic_path=ATOMIC_PATH,
                scenario_path=SCENARIO_PATH,
                manifest_path=MANIFEST_PATH,
                prompt_variant="m3.prompt.v3.supersession-guard",
                case_ids=case_ids,
                candidate_kind=f"s12-s77-{variant}-model-comparison",
            )
            run_path = RUNS_DIR / f"{variant}-run-{run_number:02d}.report.v1.json"
            variants[variant].append(write_report(run_path, report))

    control = aggregate(variants["control"], control_model)
    candidate = aggregate(variants["candidate"], candidate_model)
    deltas = {
        "entityMacroF1": candidate["meanMetrics"]["entityMacroF1"]
        - control["meanMetrics"]["entityMacroF1"],
        "relationMacroF1": candidate["meanMetrics"]["relationMacroF1"]
        - control["meanMetrics"]["relationMacroF1"],
        "abstentionAccuracy": candidate["meanMetrics"]["abstentionAccuracy"]
        - control["meanMetrics"]["abstentionAccuracy"],
        "hallucinationRateReduction": control["meanMetrics"]["hallucinationRate"]
        - candidate["meanMetrics"]["hallucinationRate"],
    }
    thresholds = prereg["semanticThresholds"]
    semantic_gates = {
        "entityMacroF1": deltas["entityMacroF1"]
        >= float(thresholds["entityMacroF1MinimumDelta"]),
        "abstentionAccuracy": deltas["abstentionAccuracy"]
        >= float(thresholds["abstentionAccuracyMinimumDelta"]),
        "hallucinationRate": deltas["hallucinationRateReduction"]
        >= float(thresholds["hallucinationRateMaximumIncrease"]),
        "relationMacroF1": deltas["relationMacroF1"]
        >= float(thresholds["relationMacroF1MinimumDelta"]),
    }
    cost_values = [
        float(run["configuration"].get("costUsd", 0.0))
        for variant in variants.values()
        for run in variant
    ]
    accounting = {
        "latencyPresent": True,
        "usagePresent": True,
        "costAccountingStatus": (
            "AVAILABLE" if any(cost_values) else "NOT_AVAILABLE_PROVIDER_PRICE_CONFIGURATION"
        ),
    }
    all_hard = bool(control["hardGatesPass"] and candidate["hardGatesPass"])
    semantic_pass = all(semantic_gates.values())
    artifact = {
        "artifactVersion": "s12.s77.model-stage-a.v1",
        "status": "STAGE_A_COMPLETED",
        "experimentId": "s12-f-05",
        "taskId": "S12-77",
        "datasetVersion": prereg["datasetVersion"],
        "datasetManifestDigest": prereg["datasetManifestDigest"],
        "preregistrationDigest": file_digest(PREREG_PATH),
        "protocol": prereg["stageA"],
        "control": control,
        "candidate": candidate,
        "comparison": {
            "metricDeltas": deltas,
            "semanticGates": semantic_gates,
            "semanticGatesPass": semantic_pass,
        },
        "accounting": accounting,
        "hardGatesPass": all_hard,
        "stageBAuthorized": all_hard and semantic_pass and accounting["costAccountingStatus"] == "AVAILABLE",
        "decision": (
            "STAGE_A_PASS"
            if all_hard and semantic_pass and accounting["costAccountingStatus"] == "AVAILABLE"
            else "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
        ),
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "digests": {
            "candidateRunnerCode": file_digest(ROOT / "scripts/run_sprint12_contract_candidate.py"),
            "evaluatorCode": file_digest(ROOT / "scripts/sprint12_evaluator.py"),
            "stageRunnerCode": file_digest(Path(__file__)),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": artifact["status"], "decision": artifact["decision"], "stageBAuthorized": artifact["stageBAuthorized"]}, sort_keys=True))


if __name__ == "__main__":
    main()
