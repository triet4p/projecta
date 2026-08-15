#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run one no-retry, sanitized diagnostic attempt for S12-77 failures."""

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
OUTPUT_PATH = ROOT / "evaluation/sprint-12/optimization/s12-77-targeted-diagnostics.v1.json"
TARGET_CASE_IDS = ("s12-a-0121", "s12-a-0176")
EXPECTED_MODEL = "deepseek-v4-pro"


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


def main() -> None:
    if OUTPUT_PATH.exists():
        raise SystemExit(f"refusing to overwrite diagnostic: {OUTPUT_PATH}")
    load_dotenv()
    missing_runtime = evaluator.missing_runtime_configuration(dict(os.environ))
    if missing_runtime:
        raise SystemExit(
            "runtime configuration missing; diagnostic not executed: "
            + ", ".join(missing_runtime)
        )
    model = os.environ["PROJECTA_LLM_MODEL"]
    if model != EXPECTED_MODEL:
        raise SystemExit(
            f"diagnostic must run with {EXPECTED_MODEL!r}; received {model!r}"
        )

    loaded = evaluator.load_dataset(ATOMIC_PATH, SCENARIO_PATH, MANIFEST_PATH)
    by_id = {str(case["caseId"]): case for case in loaded.cases}
    missing_cases = [case_id for case_id in TARGET_CASE_IDS if case_id not in by_id]
    if missing_cases:
        raise SystemExit("target cases absent from v2 dataset: " + ", ".join(missing_cases))
    subset = replace(loaded, cases=tuple(by_id[case_id] for case_id in TARGET_CASE_IDS))

    result = evaluator._runtime_baseline(
        subset,
        dict(os.environ),
        schema_version="m3.v2",
        operation_id="s12-f-05-targeted-diagnostic",
        profile_revision="s12-77-targeted-diagnostic",
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
        outcomes.append(
            {
                "caseId": case_id,
                "slice": operational_record.get("slice"),
                "status": case_results[case_id].get("status"),
                "failureClass": failure.get("failureClass") if failure else "none",
                "category": failure.get("category") if failure else "none",
                "sanitizedDiagnostic": diagnostic_by_id.get(case_id, {}).get(
                    "diagnostic", {}
                ),
            }
        )

    report = {
        "artifactVersion": "s12.s77.targeted-diagnostics.v1",
        "status": "DIAGNOSTIC_COMPLETED",
        "experimentId": "s12-f-05",
        "model": model,
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
        "operational": evaluator.score_operational(operational),
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
        "heldOutInspected": False,
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "model": model,
                "caseIds": report["caseIds"],
                "failureCounts": report["failureCounts"],
                "output": str(OUTPUT_PATH.relative_to(ROOT)).replace("\\", "/"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
