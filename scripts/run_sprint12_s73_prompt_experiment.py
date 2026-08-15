#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run the S12-73 supersession prompt experiment on 8 cases x 3 runs."""

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
ATOMIC_PATH = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json"
SCENARIO_PATH = ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v2.json"
MANIFEST_PATH = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"
DEFAULT_RUNS_DIR = ROOT / "evaluation/sprint-12/optimization/s12-73-prompt-supersession/runs"
DEFAULT_OUTPUT_PATH = ROOT / "evaluation/sprint-12/optimization/s12-73-prompt-supersession.v1.json"
RUN_COUNT = 3
TARGET_SLICE = "contradiction-or-supersession"
CASES_PER_SLICE = 8
METRIC_NAMES = (
    "entityMacroF1",
    "relationMacroF1",
    "abstentionAccuracy",
    "hallucinationRate",
)


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _run_once(variant: str, label: str, number: int, runs_dir: Path) -> dict[str, object]:
    run_path = runs_dir / f"{label}-run-{number:02d}.report.v1.json"
    if run_path.exists():
        raise FileExistsError(f"refusing to overwrite immutable prompt run: {run_path}")
    subprocess.run(
        [
            sys.executable,
            str(CANDIDATE_SCRIPT),
            "--atomic-path",
            str(ATOMIC_PATH),
            "--scenario-path",
            str(SCENARIO_PATH),
            "--manifest-path",
            str(MANIFEST_PATH),
            "--output-path",
            str(run_path),
            "--prompt-variant",
            variant,
            "--slices",
            TARGET_SLICE,
            "--cases-per-slice",
            str(CASES_PER_SLICE),
            "--candidate-kind",
            "s12-73-supersession-prompt-experiment",
        ],
        cwd=ROOT,
        env=dict(os.environ),
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(run_path.read_text(encoding="utf-8"))
    operational = report["operational"]
    failures = report["failures"]
    return {
        "runId": f"{label}-run-{number:02d}",
        "reportPath": run_path.relative_to(ROOT).as_posix(),
        "reportDigest": _file_digest(run_path),
        "status": report["status"],
        "caseCount": report["caseCount"],
        "failureCount": report["failureCount"],
        "failureCounts": dict(operational.get("failureCounts", {})),
        "failureClassByCaseId": {
            str(item["caseId"]): str(item["failureClass"])
            for item in failures
            if isinstance(item, dict)
        },
        "metrics": {
            name: report["metrics"].get(name, 0.0) for name in METRIC_NAMES
        },
        "goldPositiveCounts": report["goldPositiveCounts"],
        "configuration": report["configuration"],
        "digests": report["digests"],
    }


def _aggregate(runs: list[dict[str, object]]) -> dict[str, object]:
    return {
        "failureCounts": {
            name: sum(int(run.get("failureCounts", {}).get(name, 0)) for run in runs)
            for name in ("schema_invalid", "invalid_evidence")
        },
        "metricMeanVariance": {
            name: {
                "mean": fmean([float(run["metrics"][name]) for run in runs]),
                "min": min(float(run["metrics"][name]) for run in runs),
                "max": max(float(run["metrics"][name]) for run in runs),
                "populationVariance": pvariance(
                    [float(run["metrics"][name]) for run in runs]
                ),
            }
            for name in METRIC_NAMES
        },
        "fixedEvidenceDigests": all(
            run["digests"] == runs[0]["digests"] for run in runs
        ),
        "fixedModelSamplingConfiguration": all(
            {
                key: run["configuration"].get(key)
                for key in ("model", "baseUrl", "schemaVersion", "samplingConfiguration")
            }
            == {
                key: runs[0]["configuration"].get(key)
                for key in ("model", "baseUrl", "schemaVersion", "samplingConfiguration")
            }
            for run in runs
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    if args.output_path.exists():
        raise SystemExit(f"refusing to overwrite immutable experiment artifact: {args.output_path}")
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    baseline_runs = [
        _run_once("m3.prompt.v2", "baseline", number, args.runs_dir)
        for number in range(1, RUN_COUNT + 1)
    ]
    candidate_runs = [
        _run_once("m3.prompt.v3.supersession-guard", "candidate", number, args.runs_dir)
        for number in range(1, RUN_COUNT + 1)
    ]
    baseline = _aggregate(baseline_runs)
    candidate = _aggregate(candidate_runs)
    baseline_means = baseline["metricMeanVariance"]
    candidate_means = candidate["metricMeanVariance"]
    semantic_delta = {
        "entityMacroF1": candidate_means["entityMacroF1"]["mean"]
        - baseline_means["entityMacroF1"]["mean"],
        "relationMacroF1": candidate_means["relationMacroF1"]["mean"]
        - baseline_means["relationMacroF1"]["mean"],
        "abstentionAccuracy": candidate_means["abstentionAccuracy"]["mean"]
        - baseline_means["abstentionAccuracy"]["mean"],
        "hallucinationRateReduction": baseline_means["hallucinationRate"]["mean"]
        - candidate_means["hallucinationRate"]["mean"],
    }
    candidate_clean = all(
        candidate["failureCounts"].get(name, 0) == 0
        for name in ("schema_invalid", "invalid_evidence")
    )
    semantic_improved = (
        semantic_delta["entityMacroF1"] > 0
        and semantic_delta["abstentionAccuracy"] >= 0
        and semantic_delta["hallucinationRateReduction"] >= 0
    )
    result = {
        "schemaVersion": "s12.s12-73-prompt-experiment.v1",
        "status": "PROMPT_EXPERIMENT_COMPLETED_CANDIDATE_NOT_PROMOTED",
        "experimentId": "s12-f-01",
        "datasetVersion": "s12.corpus.atomic.v2",
        "datasetManifestDigest": manifest["manifestDigest"],
        "slice": TARGET_SLICE,
        "caseCountPerRun": CASES_PER_SLICE,
        "independentRunCountPerVariant": RUN_COUNT,
        "totalCaseExecutions": RUN_COUNT * CASES_PER_SLICE * 2,
        "baseline": {**baseline, "runs": baseline_runs},
        "candidate": {**candidate, "runs": candidate_runs},
        "semanticDelta": semantic_delta,
        "candidateSchemaEvidenceClean": candidate_clean,
        "semanticMetricsImproved": semantic_improved,
        "goldPositiveLinkCount": baseline_runs[0]["goldPositiveCounts"]["links"],
        "linkMetricUsable": baseline_runs[0]["goldPositiveCounts"]["links"] > 0,
        "linkMetricReason": "all eight supersession cases have zero positive link gold; linkMacroF1 is non-discriminating",
        "nextAction": (
            "run 32-case stability only if candidate schema/evidence is clean and semantic metrics improve"
            if candidate_clean and semantic_improved
            else "do not run 32-case prompt follow-up; revise prompt/contract diagnosis"
        ),
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
                "candidateSchemaEvidenceClean": candidate_clean,
                "semanticMetricsImproved": semantic_improved,
                "nextAction": result["nextAction"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
