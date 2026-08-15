#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Derive paired-case metrics and governance corrections for S12-f-06."""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
STAGE_A = OPTIMIZATION / "s12-f-06-sampling-stage-a.v1.json"
RUNS_DIR = OPTIMIZATION / "s12-f-06-sampling-stage-a"
OUTPUT = OPTIMIZATION / "s12-f-06-sampling-erratum.v1.json"
METRIC_NAMES = (
    "entityMacroF1",
    "relationMacroF1",
    "abstentionAccuracy",
    "hallucinationRate",
    "linkMacroF1",
)


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def metric_value(case: dict[str, object], name: str) -> float:
    if name == "entityMacroF1":
        return float(case["entities"]["f1"])
    if name == "relationMacroF1":
        return float(case["relations"]["f1"])
    if name == "linkMacroF1":
        return float(case["links"]["f1"])
    return float(case[name])


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite erratum: {OUTPUT}")
    stage = json.loads(STAGE_A.read_text(encoding="utf-8"))
    rows: list[tuple[int, str, dict[str, object], dict[str, object]]] = []
    run_counts: dict[str, int] = {}
    report_digests: dict[str, str] = {}
    for run_number in range(1, 4):
        control_path = RUNS_DIR / f"control-run-{run_number:02d}.report.v1.json"
        candidate_path = RUNS_DIR / f"candidate-run-{run_number:02d}.report.v1.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        report_digests[f"control-run-{run_number:02d}"] = file_digest(control_path)
        report_digests[f"candidate-run-{run_number:02d}"] = file_digest(candidate_path)
        control_cases = control["metrics"]["perCase"]
        candidate_cases = candidate["metrics"]["perCase"]
        common_ids = sorted(set(control_cases) & set(candidate_cases))
        common_ids = [
            case_id
            for case_id in common_ids
            if control_cases[case_id].get("status") == "scored"
            and candidate_cases[case_id].get("status") == "scored"
        ]
        run_counts[f"run-{run_number:02d}"] = len(common_ids)
        rows.extend(
            (run_number, case_id, control_cases[case_id], candidate_cases[case_id])
            for case_id in common_ids
        )

    common_metrics: dict[str, dict[str, float]] = {}
    for name in METRIC_NAMES:
        control_mean = statistics.fmean(metric_value(row[2], name) for row in rows)
        candidate_mean = statistics.fmean(metric_value(row[3], name) for row in rows)
        common_metrics[name] = {
            "control": control_mean,
            "candidate": candidate_mean,
            "delta": candidate_mean - control_mean,
        }
    common_metrics["hallucinationRateReduction"] = {
        "control": common_metrics["hallucinationRate"]["control"],
        "candidate": common_metrics["hallucinationRate"]["candidate"],
        "delta": common_metrics["hallucinationRate"]["control"]
        - common_metrics["hallucinationRate"]["candidate"],
    }

    report = {
        "artifactVersion": "s12.s12-f-06.erratum.v1",
        "status": "ERRATUM_ISSUED_WITHOUT_RERUN",
        "experimentId": "s12-f-06",
        "sourceArtifact": {
            "artifact": STAGE_A.name,
            "digest": file_digest(STAGE_A),
        },
        "candidateHardGates": "PASS",
        "controlHardGates": "FAIL",
        "comparisonIntegrity": "DEGRADED_UNEQUAL_VALID_OUTPUTS",
        "semanticGates": stage["comparison"]["semanticGates"],
        "historicalAggregate": {
            "method": "UNEQUAL_DENOMINATOR_VALID_OUTPUT_MEANS",
            "metricDeltas": stage["comparison"]["metricDeltas"],
            "interpretation": (
                "Retained for historical traceability; control and candidate means "
                "were computed over different valid-output denominators."
            ),
        },
        "commonCaseMetrics": {
            "method": "COMMON_VALID_OUTPUT_CASES_PER_PAIRED_RUN",
            "caseExecutionCount": len(rows),
            "caseCountByRun": run_counts,
            "metrics": common_metrics,
        },
        "decision": "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B",
        "reportDigests": report_digests,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "commonCaseExecutionCount": len(rows),
                "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
