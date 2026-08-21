"""Contract tests for the non-provider S12-f-09 Stage A preflight."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "evaluation/sprint-12/gates/s12-f-09-stage-a-preflight.v1.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_preflight_is_ready_but_owner_authorization_is_still_missing() -> None:
    report = read_json(PREFLIGHT)
    assert report["reportVersion"] == "s12.f09.stage-a-preflight.v1"
    assert report["status"] == "READY_PENDING_OWNER_AUTHORIZATION"
    assert report["checks"]["ownerAuthorization"] is False
    assert all(value for key, value in report["checks"].items() if key != "ownerAuthorization")
    assert report["execution"]["providerExecutionAuthorized"] is False
    assert report["execution"]["providerCallsPerformed"] is False
    assert report["execution"]["heldOutInspected"] is False


def test_preflight_binds_f09_stage_a_without_creating_execution_package() -> None:
    execution = read_json(PREFLIGHT)["execution"]
    bound = read_json(PREFLIGHT)["boundExperiment"]
    assert execution["executionPackageCreated"] is False
    assert bound["experimentId"] == "s12-f-09"
    assert bound["datasetVersion"] == "s12.corpus.atomic.v3.frozen"
    assert bound["caseCount"] == 48
    assert bound["caseRunsPerArm"] == 144
    assert bound["costCeilingUsd"] == "10.00"
