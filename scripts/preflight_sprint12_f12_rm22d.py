"""Zero-call preflight for the RM-22D superseding v5 lineage."""

from __future__ import annotations

import json
from decimal import Decimal

import preflight_sprint12_f12_rm22c as base
import run_sprint12_f12_stage_a_v5 as v5


def run_preflight() -> dict[str, object]:
    base.v4 = v5
    v5._configure()
    base.PACKAGE = v5.PACKAGE
    base.PREREG = v5.PREREG
    base.FREEZE = v5.FREEZE
    base.OUTPUT = v5.OUTPUT
    base.run_stage_a = v5.run_stage_a
    package = v5.v4.v3.load(v5.PACKAGE)
    prereg = v5.v4.v3.load(v5.PREREG)
    freeze = v5.v4.v3.load(v5.FREEZE)
    for artifact in (package, prereg, freeze):
        if artifact.get("experimentId") != "s12-f-12":
            raise ValueError("RM-22D artifact experimentId is not exact")
        if any(
            artifact.get(key) is not False
            for key in (
                "heldOutInspected",
                "heldOutAccessAuthorized",
                "validationAccessAuthorized",
                "stageBAuthorized",
                "candidateSelectionAuthorized",
                "promotionAuthorized",
            )
        ):
            raise ValueError("RM-22D artifact governance scope is open")
    result = base.run_preflight()
    if Decimal(str(prereg["pricing"]["costCeilingUsd"])) != Decimal("10.00"):
        raise ValueError("RM-22D cost ceiling is not exact")
    auth_schema = v5.AUTHORIZATION_SCHEMA
    if not auth_schema.is_file():
        raise ValueError("RM-22D authorization schema is missing")
    if v5.OUTPUT.exists() or (
        v5.ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-authorization.v5.json"
    ).exists():
        raise ValueError("RM-22D output or authorization already exists")
    result["status"] = "F12_RM22D_READY_ZERO_CALL_V5"
    return result


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
