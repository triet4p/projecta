"""Zero-call preflight for the RM-22C superseding v4 lineage."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import preflight_sprint12_f12_rm22b as base
import run_sprint12_f12_stage_a_v4 as v4


def _derive_denominators_at_commit(commit_sha: str) -> dict[str, Any]:
    derived = base._derive_denominators_at_commit(commit_sha)
    corpus = base._json_at_commit(
        commit_sha, "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
    )
    selection = base._json_at_commit(
        commit_sha, "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
    )
    ids = list(selection["caseIds"])
    cases = [case for case in corpus["cases"] if case["caseId"] in ids]
    hard_negative = [
        case
        for case in cases
        if not case["gold"]["relations"]
        and not case["gold"]["abstention"]["required"]
    ]
    derived["namedSliceDenominators"]["relation-negative"] = len(hard_negative) * 3
    return derived


def run_preflight() -> dict[str, Any]:
    v4._configure()
    base.PACKAGE = v4.PACKAGE
    base.PREREG = v4.PREREG
    base.FREEZE = v4.FREEZE
    base.OUTPUT = v4.OUTPUT
    base.run_stage_a = v4.run_stage_a
    base._derive_denominators_at_commit = _derive_denominators_at_commit
    package = v4.v3.load(v4.PACKAGE)
    prereg = v4.v3.load(v4.PREREG)
    freeze = v4.v3.load(v4.FREEZE)
    for artifact in (package, prereg, freeze):
        if artifact.get("experimentId") != "s12-f-12":
            raise ValueError("RM-22C artifact experimentId is not exact")
        if any(
            artifact.get(key) is not False
            for key in (
                "heldOutInspected",
                "stageBAuthorized",
                "candidateSelectionAuthorized",
                "promotionAuthorized",
            )
        ):
            raise ValueError("RM-22C artifact governance scope is open")
    result = base.run_preflight()
    if any(
        prereg.get(key) is not False
        for key in (
            "heldOutInspected",
            "stageBAuthorized",
            "candidateSelectionAuthorized",
            "promotionAuthorized",
        )
    ):
        raise ValueError("RM-22C preregistration governance scope is open")
    if v4.OUTPUT.exists() or (
        v4.ROOT
        / "evaluation/sprint-12/optimization/s12-f-12-rm22c-authorization.v4.json"
    ).exists():
        raise ValueError("RM-22C output or authorization already exists")
    if Decimal(str(prereg["pricing"]["costCeilingUsd"])) != Decimal("10.00"):
        raise ValueError("RM-22C cost ceiling is not exact")
    result["status"] = "F12_RM22C_READY_ZERO_CALL_V4"
    return result


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
