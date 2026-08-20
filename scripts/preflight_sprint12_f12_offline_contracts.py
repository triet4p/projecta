#!/usr/bin/env -S uv run --script
"""Zero-call preflight for the conditionally approved S12-f-12 design."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-12-two-step-extraction-design-proposal.v1.json"
)
REVIEW = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-12-two-step-extraction-design-review.v1.json"
)
FIXTURES = ROOT / "evaluation/sprint-12/harness/s12-f-12-oracle-fixtures.v1.json"
STAGE1_SCHEMA = (
    ROOT
    / "evaluation/sprint-12/harness/s12-f-12-stage-1-entity-candidate.schema.v1.json"
)
STAGE2_SCHEMA = (
    ROOT
    / "evaluation/sprint-12/harness/s12-f-12-stage-2-relation-candidate.schema.v1.json"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact is not an object: {path}")
    return value


def run_preflight() -> dict[str, Any]:
    proposal = _load(PROPOSAL)
    review = _load(REVIEW)
    fixtures = _load(FIXTURES)
    stage1 = _load(STAGE1_SCHEMA)
    stage2 = _load(STAGE2_SCHEMA)
    if proposal.get("status") != "DRAFT_PENDING_OWNER_REVIEW":
        raise ValueError("f12 proposal is not review-only")
    if review.get("governance", {}).get("providerExecutionAuthorized") is not False:
        raise ValueError("f12 review opens provider execution")
    if review.get("governance", {}).get("preregistrationAuthorized") is not False:
        raise ValueError("f12 review opens preregistration")
    if (
        proposal.get("custodyAndGovernance", {}).get("newPreregistrationIssued")
        is not False
    ):
        raise ValueError("f12 proposal claims a preregistration")
    for schema in (stage1, stage2):
        if schema.get("additionalProperties") is not False:
            raise ValueError("stage schema permits unbound fields")
    if fixtures.get("rawSourceTextIncluded") is not False:
        raise ValueError("oracle fixtures contain raw source text")
    if not fixtures.get("fixtures"):
        raise ValueError("oracle fixtures are empty")
    if list(
        ROOT.glob("evaluation/sprint-12/optimization/s12-f-12-*-authorization*.json")
    ):
        raise ValueError("f12 authorization artifact exists")
    if list(
        ROOT.glob("evaluation/sprint-12/optimization/s12-f-12-*-preregistration*.json")
    ):
        raise ValueError("f12 preregistration artifact exists")
    return {
        "status": "OFFLINE_CONTRACTS_READY_ZERO_CALL",
        "experimentId": "s12-f-12",
        "providerCalls": 0,
        "providerExecutionAuthorized": False,
        "preregistrationIssued": False,
        "heldOutAccess": False,
        "oracleFixtureCount": len(fixtures["fixtures"]),
        "stageSchemas": [stage1["$id"], stage2["$id"]],
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), indent=2, sort_keys=True))
