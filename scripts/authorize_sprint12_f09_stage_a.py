#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Record explicit owner authorization for the bounded f09 Stage A run."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
GATES = ROOT / "evaluation/sprint-12/gates"
FROZEN = ROOT / "evaluation/sprint-12/corpus/v3-frozen"
PREREG = OPT / "s12-f-09-relation-evidence-preregistration.v1.json"
PREFLIGHT = GATES / "s12-f-09-stage-a-preflight.v1.json"
RUNNER = ROOT / "scripts/run_sprint12_f09_relation_evidence.py"
OUTPUT = OPT / "s12-f-09-authorization.v1.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"), cwd=ROOT, text=True
    ).strip()


def build_authorization() -> dict[str, Any]:
    prereg = _read(PREREG)
    preflight = _read(PREFLIGHT)
    g31b = _read(GATES / "g3.1-b-pilot-approval.v1.json")
    g31c = _read(GATES / "g3.1-c-v3-readiness.v1.json")
    qa = _read(FROZEN / "qa-report.v1.json")
    if prereg["status"] != "PREREGISTERED_NOT_EXECUTED":
        raise SystemExit("f09 preregistration is not in immutable pre-execution state")
    if not all(
        value
        for key, value in preflight["checks"].items()
        if key != "ownerAuthorization"
    ):
        raise SystemExit("offline f09 preflight has a failed non-owner check")
    if g31b["status"] != "G3_1_B_PILOT_APPROVED_WITH_SCOPE_LIMITS":
        raise SystemExit("G3.1-B approval is not bound")
    if g31c["status"] != "G3_1_C_READY_SCOPED_TO_J1_J6_EXTRACTION":
        raise SystemExit("G3.1-C readiness is not bound")
    if qa["status"] != "FROZEN_QA_PASS" or not all(qa["gates"].values()):
        raise SystemExit("frozen v3 QA is not passing")
    stage = prereg["stageA"]
    execution_package = dict(prereg["executionPackage"])
    return {
        "artifactVersion": "s12.s12-f-09.stage-a-authorization.v1",
        "experimentId": prereg["experimentId"],
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "authorizationSource": "explicit-owner-message",
        "authorizationStatement": "Authorize S12-f-09 Stage A theo preregistration hiện tại.",
        "authorizedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commitSha": _git_head(),
        "preregistration": {
            "path": PREREG.relative_to(ROOT).as_posix(),
            "digest": _digest(PREREG),
        },
        "executionPackage": execution_package,
        "runner": {
            "path": RUNNER.relative_to(ROOT).as_posix(),
            "digest": _digest(RUNNER),
        },
        "scope": {
            "stage": "A",
            "datasetVersion": prereg["fixedArtifacts"]["datasetVersion"],
            "split": stage["split"],
            "caseCount": stage["caseCount"],
            "caseRunsPerArm": stage["caseRunsPerArm"],
            "independentPairedRuns": stage["independentPairedRuns"],
            "oneAttemptPerCase": stage["oneAttemptPerCase"],
            "retryPolicy": prereg["fixedArtifacts"]["retryPolicy"],
            "costCeilingUsd": prereg["pricingContract"]["costCeilingUsd"],
            "controlTool": prereg["control"]["configuration"]["tool"],
            "candidateTool": prereg["candidate"]["configuration"]["tool"],
        },
        "gates": {
            "g31bApproved": True,
            "g31cReady": True,
            "frozenQaPass": True,
            "preflightNonOwnerChecksPass": True,
        },
        "providerExecutionAuthorized": True,
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "retryAuthorized": False,
        "rawSensitiveDataIncluded": False,
    }


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite authorization: {OUTPUT}")
    report = build_authorization()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"experimentId": report["experimentId"], "status": report["status"], "providerExecutionAuthorized": report["providerExecutionAuthorized"]}, indent=2))


if __name__ == "__main__":
    main()
