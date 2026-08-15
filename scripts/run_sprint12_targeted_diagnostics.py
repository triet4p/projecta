#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run one no-retry diagnostic attempt for the two recurring S12-73 failures."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sprint12_evaluator as evaluator

ATOMIC_PATH = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json"
SCENARIO_PATH = ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v2.json"
MANIFEST_PATH = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"
OUTPUT_PATH = ROOT / "evaluation/sprint-12/optimization/s12-73-targeted-diagnostics.v1.json"
TARGET_CASE_IDS = ("s12-a-0153", "s12-a-0187")


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT_PATH.exists():
        raise SystemExit(f"refusing to overwrite existing diagnostic: {OUTPUT_PATH}")
    loaded = evaluator.load_dataset(ATOMIC_PATH, SCENARIO_PATH, MANIFEST_PATH)
    by_id = {str(case["caseId"]): case for case in loaded.cases}
    missing = [case_id for case_id in TARGET_CASE_IDS if case_id not in by_id]
    if missing:
        raise SystemExit("target cases absent from v2 dataset: " + ", ".join(missing))
    subset = replace(loaded, cases=tuple(by_id[case_id] for case_id in TARGET_CASE_IDS))
    missing_runtime = evaluator.missing_runtime_configuration(dict(os.environ))
    if missing_runtime:
        raise SystemExit(
            "runtime configuration missing; diagnostic not executed: "
            + ", ".join(missing_runtime)
        )
    result = evaluator._runtime_baseline(
        subset,
        dict(os.environ),
        schema_version="m3.v2",
        operation_id="s12-f-01-targeted-diagnostic",
        profile_revision="s12-73-targeted-diagnostic",
        prompt_variant="m3.prompt.v3.supersession-guard",
        collect_diagnostics=True,
    )
    case_results, operational, failures, config, diagnostics = result
    diagnostic_by_id = {str(item["caseId"]): item for item in diagnostics}
    failure_by_id = {str(item["caseId"]): item for item in failures}
    operational_by_id = {str(item["caseId"]): item for item in operational}
    outcomes = []
    for case_id in TARGET_CASE_IDS:
        operational_record = operational_by_id[case_id]
        failure = failure_by_id.get(case_id)
        diagnostic = diagnostic_by_id.get(case_id, {}).get("diagnostic", {})
        outcomes.append(
            {
                "caseId": case_id,
                "slice": operational_record.get("slice"),
                "status": case_results[case_id].get("status"),
                "failureClass": failure.get("failureClass") if failure else "none",
                "category": failure.get("category") if failure else "none",
                "sanitizedDiagnostic": diagnostic,
            }
        )
    report = {
        "artifactVersion": "s12.s73.targeted-diagnostics.v1",
        "status": "DIAGNOSTIC_COMPLETED",
        "datasetVersion": subset.dataset.get("datasetVersion"),
        "manifestDigest": subset.manifest.get("manifestDigest"),
        "caseIds": list(TARGET_CASE_IDS),
        "caseCount": len(TARGET_CASE_IDS),
        "protocol": {
            "independentRunCount": 1,
            "oneAttemptPerCase": True,
            "noRetryWithinEachRun": True,
            "promptVariant": config.get("promptVersion"),
            "samplingConfiguration": config.get("samplingConfiguration"),
        },
        "outcomes": outcomes,
        "failureCounts": evaluator.score_operational(operational).get(
            "failureCounts", {}
        ),
        "digests": {
            "evaluatorCode": file_digest(ROOT / "scripts/sprint12_evaluator.py"),
            "diagnosticRunnerCode": file_digest(Path(__file__)),
            "gatewayContractCode": file_digest(
                ROOT / "apps/api/src/projecta_api/llm/gateway.py"
            ),
            "gatewayAdapterCode": file_digest(
                ROOT / "apps/api/src/projecta_api/llm/openai_responses.py"
            ),
            "manifest": subset.manifest.get("manifestDigest"),
        },
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "credentialIncluded": False,
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "caseIds": report["caseIds"],
                "failureCounts": report["failureCounts"],
                "output": str(OUTPUT_PATH.relative_to(ROOT)).replace("\\", "/"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
