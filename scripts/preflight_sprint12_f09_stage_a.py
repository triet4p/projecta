#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run the non-provider S12-f-09 Stage A preflight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATES = ROOT / "evaluation/sprint-12/gates"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-09-relation-evidence-preregistration.v1.json"
FROZEN = ROOT / "evaluation/sprint-12/corpus/v3-frozen"
OUTPUT = GATES / "s12-f-09-stage-a-preflight.v1.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_preflight() -> dict[str, Any]:
    prereg = _read(PREREG)
    g31b = _read(GATES / "g3.1-b-pilot-approval.v1.json")
    g31c = _read(GATES / "g3.1-c-v3-readiness.v1.json")
    qa = _read(FROZEN / "qa-report.v1.json")
    manifest = _read(FROZEN / "atomic-manifest.v1.json")
    stage = prereg["stageA"]
    checks = {
        "preregistrationReady": prereg["status"] == "PREREGISTERED_NOT_EXECUTED" and prereg["executionAuthorized"] is False,
        "g31bApproved": g31b["status"] == "G3_1_B_PILOT_APPROVED_WITH_SCOPE_LIMITS",
        "g31cReady": g31c["status"] == "G3_1_C_READY_SCOPED_TO_J1_J6_EXTRACTION",
        "frozenQaPass": qa["status"] == "FROZEN_QA_PASS" and all(qa["gates"].values()),
        "stageCasesAreDevelopment": stage["split"] == "development" and len(stage["caseIds"]) == 48,
        "manifestHasNoTestPayload": manifest["atomicCounts"]["test"] == 0 and manifest["testPayloadPresent"] is False,
        "ownerAuthorization": False,
    }
    return {
        "reportVersion": "s12.f09.stage-a-preflight.v1",
        "status": "READY_PENDING_OWNER_AUTHORIZATION" if all(checks.values()) is False and all(value for key, value in checks.items() if key != "ownerAuthorization") else "PREFLIGHT_FAILED",
        "checks": checks,
        "execution": {
            "providerExecutionAuthorized": False,
            "providerCallsPerformed": False,
            "heldOutInspected": False,
            "executionPackageCreated": False,
            "blockingConditions": ["explicit owner authorization is required before any provider call"],
        },
        "boundExperiment": {
            "experimentId": prereg["experimentId"],
            "preregistration": PREREG.name,
            "datasetVersion": prereg["fixedArtifacts"]["datasetVersion"],
            "caseCount": stage["caseCount"],
            "caseRunsPerArm": stage["caseRunsPerArm"],
            "costCeilingUsd": prereg["pricingContract"]["costCeilingUsd"],
        },
    }


def main() -> None:
    report = build_preflight()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "providerExecutionAuthorized": report["execution"]["providerExecutionAuthorized"]}, indent=2))


if __name__ == "__main__":
    main()
