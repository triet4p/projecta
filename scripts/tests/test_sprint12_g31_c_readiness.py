"""Contract tests for the scoped G3.1-C readiness approval."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "evaluation/sprint-12/gates/g3.1-c-v3-readiness.v1.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_g31_c_ready_for_scoped_controlled_runs_only() -> None:
    report = read_json(REPORT)
    assert report["reportVersion"] == "s12.g31-c-v3-readiness.v1"
    assert report["status"] == "G3_1_C_READY_SCOPED_TO_J1_J6_EXTRACTION"
    assert all(report["gates"].values())
    assert report["scope"]["controlledDevelopment"] is True
    assert report["scope"]["oneValidationRun"] is True
    assert report["scope"]["representedJourneys"] == ["J1", "J2", "J3", "J4", "J5", "J6"]
    assert report["scope"]["excludedJourneys"] == ["J7", "J8"]
    assert report["scope"]["benchmarkCompleteness"] is False


def test_g31_c_meets_visible_minimums_and_language_minimums() -> None:
    report = read_json(REPORT)
    assert report["coverage"]["atomicCounts"] == {"development": 160, "validation": 48, "test": 0, "total": 208}
    assert report["coverage"]["scenarioCounts"] == {"development": 20, "validation": 6, "test": 0, "total": 26}
    assert report["coverage"]["languageCounts"] == {"vi": 87, "en": 41, "ja": 26, "mixed": 54}
    assert all(row["pass"] for row in report["coverage"]["journeyChecks"].values() if row["atomicObserved"])


def test_g31_c_does_not_authorize_provider_or_heldout() -> None:
    authorization = read_json(REPORT)["authorization"]
    assert authorization["providerExecutionAuthorized"] is False
    assert authorization["heldOutAccessAuthorized"] is False
    assert authorization["testPayloadRead"] is False
