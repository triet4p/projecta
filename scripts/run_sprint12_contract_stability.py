#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run an immutable three-run stability gate over the development subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from statistics import fmean, pvariance

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SCRIPT = ROOT / "scripts/run_sprint12_contract_candidate.py"
DEFAULT_ATOMIC_PATH = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json"
DEFAULT_SCENARIO_PATH = ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v2.json"
DEFAULT_MANIFEST_PATH = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"
DEFAULT_RUNS_DIR = ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-stability/runs"
DEFAULT_OUTPUT_PATH = ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-stability.v2.json"
RUN_COUNT = 3
METRIC_NAMES = (
    "entityMacroF1",
    "relationMacroF1",
    "linkMacroF1",
    "abstentionAccuracy",
    "hallucinationRate",
)


def _metric_variance(values: list[float]) -> dict[str, float]:
    return {
        "mean": fmean(values) if values else 0.0,
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "populationVariance": pvariance(values) if len(values) > 1 else 0.0,
    }


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _run_once(
    run_number: int,
    *,
    atomic_path: Path,
    scenario_path: Path,
    manifest_path: Path,
    runs_dir: Path,
    prompt_variant: str,
) -> dict[str, object]:
    run_path = runs_dir / f"run-{run_number:02d}.report.v1.json"
    if run_path.exists():
        raise FileExistsError(f"refusing to overwrite immutable run report: {run_path}")
    environment = dict(os.environ)
    subprocess.run(
        [
            sys.executable,
            str(CANDIDATE_SCRIPT),
            "--atomic-path",
            str(atomic_path),
            "--scenario-path",
            str(scenario_path),
            "--manifest-path",
            str(manifest_path),
            "--output-path",
            str(run_path),
            "--prompt-variant",
            prompt_variant,
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(run_path.read_text(encoding="utf-8"))
    operational = report.get("operational", {})
    metrics = report.get("metrics", {})
    failures = report.get("failures", [])
    configuration = report.get("configuration", {})
    digests = report.get("digests", {})
    if not all(isinstance(item, dict) for item in (operational, metrics, configuration, digests)):
        raise TypeError("run report accounting, configuration or digests is malformed")
    if not isinstance(failures, list):
        raise TypeError("run report failures must be a list")
    failure_counts = operational.get("failureCounts", {})
    if not isinstance(failure_counts, dict):
        raise TypeError("run report failureCounts must be an object")
    failure_by_case = {
        str(item["caseId"]): str(item["failureClass"])
        for item in failures
        if isinstance(item, dict) and "caseId" in item and "failureClass" in item
    }
    return {
        "runId": f"run-{run_number:02d}",
        "reportPath": run_path.relative_to(ROOT).as_posix(),
        "reportDigest": _file_digest(run_path),
        "datasetVersion": report.get("datasetVersion"),
        "status": report.get("status"),
        "caseCount": report.get("caseCount"),
        "failureCount": report.get("failureCount"),
        "failureCounts": dict(failure_counts),
        "failureClassByCaseId": failure_by_case,
        "metrics": {
            name: metrics.get(name, 0.0)
            for name in METRIC_NAMES
            if isinstance(metrics.get(name), (int, float))
        },
        "configuration": dict(configuration),
        "digests": dict(digests),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atomic-path", type=Path, default=DEFAULT_ATOMIC_PATH)
    parser.add_argument("--scenario-path", type=Path, default=DEFAULT_SCENARIO_PATH)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--prompt-variant", default="m3.prompt.v2")
    parser.add_argument("--run-count", type=int, default=RUN_COUNT)
    args = parser.parse_args()
    args.atomic_path = args.atomic_path.resolve()
    args.scenario_path = args.scenario_path.resolve()
    args.manifest_path = args.manifest_path.resolve()
    args.runs_dir = args.runs_dir.resolve()
    args.output_path = args.output_path.resolve()
    if args.output_path.exists():
        raise SystemExit(f"refusing to overwrite immutable stability artifact: {args.output_path}")
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    runs = [
        _run_once(
            number,
            atomic_path=args.atomic_path,
            scenario_path=args.scenario_path,
            manifest_path=args.manifest_path,
            runs_dir=args.runs_dir,
            prompt_variant=args.prompt_variant,
        )
        for number in range(1, args.run_count + 1)
    ]
    configurations = [run["configuration"] for run in runs]
    digests = [run["digests"] for run in runs]
    fixed_configuration = all(config == configurations[0] for config in configurations)
    fixed_digests = all(item == digests[0] for item in digests)
    metric_variance = {
        name: _metric_variance(
            [
                float(run["metrics"].get(name, 0.0))
                for run in runs
                if isinstance(run.get("metrics"), dict)
            ]
        )
        for name in METRIC_NAMES
    }
    total_executions = sum(int(run.get("caseCount", 0)) for run in runs)
    total_schema_invalid = sum(
        int(run.get("failureCounts", {}).get("schema_invalid", 0)) for run in runs
    )
    total_invalid_evidence = sum(
        int(run.get("failureCounts", {}).get("invalid_evidence", 0)) for run in runs
    )
    gate_pass = (
        fixed_configuration
        and fixed_digests
        and all(
            run.get("failureCounts", {}).get("schema_invalid", 0) == 0
            and run.get("failureCounts", {}).get("invalid_evidence", 0) == 0
            for run in runs
        )
    )
    result = {
        "schemaVersion": "s12.contract-candidate-v2-stability.v2",
        "status": "STABILITY_GATE_PASS" if gate_pass else "STABILITY_GATE_FAIL",
        "contractVersion": "m3.v2",
        "datasetVersion": runs[0].get("datasetVersion"),
        "independentRunCount": len(runs),
        "caseCountPerRun": runs[0].get("caseCount"),
        "totalCaseExecutions": total_executions,
        "retryPolicy": "none",
        "noRetryWithinEachRun": all(
            run.get("configuration", {}).get("retryPolicy") == "none"
            and run.get("configuration", {}).get("oneAttemptPerCase") is True
            for run in runs
        ),
        "fixedModelConfiguration": fixed_configuration,
        "fixedEvidenceDigests": fixed_digests,
        "samplingConfiguration": configurations[0].get("samplingConfiguration"),
        "aggregateFailureCounts": {
            "schema_invalid": total_schema_invalid,
            "invalid_evidence": total_invalid_evidence,
        },
        "metricVariance": metric_variance,
        "runs": runs,
        "validationAuthorized": False,
        "candidateFreezeAuthorized": False,
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "totalCaseExecutions": total_executions,
                "schema_invalid": total_schema_invalid,
                "invalid_evidence": total_invalid_evidence,
                "fixedEvidenceDigests": fixed_digests,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
