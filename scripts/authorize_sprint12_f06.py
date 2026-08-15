#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Record user authorization for the bounded S12-f-06 Stage A run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
PREREGISTRATION = OPTIMIZATION / "s12-f-06-sampling-preregistration.v1.json"
AUTHORIZATION = OPTIMIZATION / "s12-f-06-sampling-authorization.v1.json"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if AUTHORIZATION.exists():
        raise SystemExit(f"refusing to overwrite authorization: {AUTHORIZATION}")
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    if preregistration["status"] != "PREREGISTERED_NOT_EXECUTED":
        raise SystemExit("S12-f-06 preregistration is not in the expected state")
    authorization = {
        "artifactVersion": "s12.s12-f-06.authorization.v1",
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "experimentId": "s12-f-06",
        "approvalSource": "current-user-instruction",
        "scope": {
            "stage": "A",
            "caseCount": preregistration["stageA"]["caseCount"],
            "independentRunsPerVariant": preregistration["stageA"][
                "independentRunsPerVariant"
            ],
            "oneAttemptPerCase": True,
            "noRetryWithinEachRun": True,
            "developmentOnly": True,
            "stageBAuthorized": False,
            "validationAuthorized": False,
            "heldOutInspected": False,
        },
        "preregistration": {
            "artifact": PREREGISTRATION.name,
            "digest": file_digest(PREREGISTRATION),
        },
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "credentialIncluded": False,
    }
    AUTHORIZATION.write_text(
        json.dumps(authorization, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": authorization["status"], "experimentId": "s12-f-06"}))


if __name__ == "__main__":
    main()
