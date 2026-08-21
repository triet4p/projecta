#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Bind the offline evidence for the Sprint 12 G3.1-A measurement gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_VERSION = "s12.g31-a-readiness.v1"
REQUIRED_TASKS = tuple(f"S12-R{number:02d}" for number in range(1, 8))
FORBIDDEN_REPORT_TOKENS = ("rawText", "candidateId", "entityId", "apiKey")

ARTIFACTS = {
    "coreAudit": "evaluation/sprint-12/audit/core-quality-audit.v1.json",
    "metricContract": "evaluation/sprint-12/harness/metric-contract.v2.json",
    "metricDefinitions": "evaluation/sprint-12/harness/metrics.v2.md",
    "evaluator": "scripts/sprint12_evaluator.py",
    "relationInstrumentationTests": "scripts/tests/test_sprint12_relation_instrumentation_v3.py",
    "sanitizedSignatureTests": "scripts/tests/test_sprint12_sanitized_signatures.py",
    "leakageValidator": "scripts/sprint12_leakage_validator.py",
    "languageValidator": "scripts/sprint12_language_validator.py",
    "scenarioValidator": "scripts/sprint12_scenario_validator.py",
    "leakageReport": "evaluation/sprint-12/corpus/validation/leakage-report.v2.json",
    "languageReport": "evaluation/sprint-12/corpus/validation/language-report.v2.json",
    "scenarioReport": "evaluation/sprint-12/corpus/validation/scenario-report.v2.json",
}
REPORT_IDS = ("leakageReport", "languageReport", "scenarioReport")


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _contains_forbidden_token(value: object) -> str | None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return next(
        (token for token in FORBIDDEN_REPORT_TOKENS if token in serialized), None
    )


def _bind_artifacts(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    bindings = []
    failures = []
    for artifact_id, relative_path in ARTIFACTS.items():
        path = root / relative_path
        if not path.exists():
            failures.append(f"missing artifact: {relative_path}")
            continue
        bindings.append(
            {
                "id": artifact_id,
                "path": path.relative_to(root).as_posix(),
                "digest": _sha256(path),
            }
        )
    return bindings, failures


def build_readiness(root: Path = ROOT) -> dict[str, Any]:
    bindings, failures = _bind_artifacts(root)
    plan_path = root / "docs/sprint-plans/sprint-12.md"
    plan = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
    for task_id in REQUIRED_TASKS:
        if f"[x] **{task_id}" not in plan:
            failures.append(f"prerequisite not complete: {task_id}")

    metric_path = root / ARTIFACTS["metricContract"]
    if metric_path.exists():
        metric = _read_json(metric_path)
        if metric.get("version") != "s12.metric-contract.v2":
            failures.append("metric contract version is not v2")
        if metric.get("providerExecutionAuthorized") is not False:
            failures.append("metric contract authorizes provider execution")

    evaluator_path = root / ARTIFACTS["evaluator"]
    if evaluator_path.exists():
        evaluator_source = evaluator_path.read_text(encoding="utf-8")
        if 'EVALUATOR_VERSION = "s12.evaluator.v4"' not in evaluator_source:
            failures.append("current evaluator v4 binding is missing")
        if "s12.relation-instrumentation.v4" not in evaluator_source:
            failures.append("current relation instrumentation v4 binding is missing")

    diagnostic_reports = []
    expected_statuses = {
        "leakageReport": "BLOCKED_KNOWN_LEAKAGE",
        "languageReport": "BLOCKED_LANGUAGE_METADATA",
        "scenarioReport": "BLOCKED_SCENARIO_INCONSISTENCY",
    }
    for report_id in REPORT_IDS:
        report_path = root / ARTIFACTS[report_id]
        if not report_path.exists():
            continue
        report = _read_json(report_path)
        forbidden = _contains_forbidden_token(report)
        if forbidden:
            failures.append(f"{report_id} contains forbidden token: {forbidden}")
        if report.get("status") != expected_statuses[report_id]:
            failures.append(f"unexpected status in {report_id}")
        read_scope = report.get("readScope", {})
        if read_scope.get("testPayloadRead") is not False:
            failures.append(f"{report_id} does not prove test payload was not read")
        diagnostic_reports.append(
            {
                "id": report_id,
                "path": report_path.relative_to(root).as_posix(),
                "digest": _sha256(report_path),
                "status": report.get("status"),
                "testPayloadRead": read_scope.get("testPayloadRead"),
            }
        )

    return {
        "reportVersion": VALIDATOR_VERSION,
        "status": "G3.1_A_MEASUREMENT_READY_DATASET_REMEDIATION_REQUIRED"
        if not failures
        else "G3.1_A_MEASUREMENT_NOT_READY",
        "measurementGate": {
            "pass": not failures,
            "providerExecutionAuthorized": False,
            "heldOutInspected": False,
            "providerCallsPerformed": False,
        },
        "bindings": bindings,
        "diagnosticReports": diagnostic_reports,
        "requiredPrerequisiteTasks": list(REQUIRED_TASKS),
        "testEvidence": {
            "fullSuiteCommand": "PYTHONPATH=. uv run --project apps/api pytest -q scripts/tests",
            "targetedContracts": [
                "test_sprint12_relation_instrumentation_v3.py",
                "test_sprint12_sanitized_signatures.py",
                "test_sprint12_leakage_validator_v2.py",
                "test_sprint12_language_validator_v2.py",
                "test_sprint12_scenario_validator_v2.py",
            ],
            "ruffCommand": "uv run --project apps/api ruff check <changed Python files>",
            "diffCheckCommand": "git diff --check",
        },
        "residualLimitations": [
            "The v2 atomic and scenario corpora remain historical synthetic fixtures and are not business benchmarks.",
            "The v2 corpus remains blocked by normalized-template overlap, language metadata mismatches, and scenario lineage conflicts.",
            "The repository has no qualified independent language or scenario adjudication evidence.",
            "Test payload and gold remain sealed and were not inspected.",
            "G3.1-B and G3.1-C are still required before any provider execution or G5-R experiment.",
        ],
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_readiness()
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
