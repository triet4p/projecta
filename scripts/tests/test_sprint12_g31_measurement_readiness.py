"""Contract tests for the Sprint 12 G3.1-A measurement readiness packet."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_g31_measurement_readiness",
    ROOT / "scripts/sprint12_g31_measurement_readiness.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_g31_a_measurement_packet_is_ready_but_provider_remains_blocked() -> None:
    report = MODULE.build_readiness()
    assert report["reportVersion"] == "s12.g31-a-readiness.v1"
    assert report["status"] == "G3.1_A_MEASUREMENT_READY_DATASET_REMEDIATION_REQUIRED"
    assert report["measurementGate"] == {
        "pass": True,
        "providerExecutionAuthorized": False,
        "heldOutInspected": False,
        "providerCallsPerformed": False,
    }
    assert {row["status"] for row in report["diagnosticReports"]} == {
        "BLOCKED_KNOWN_LEAKAGE",
        "BLOCKED_LANGUAGE_METADATA",
        "BLOCKED_SCENARIO_INCONSISTENCY",
    }
    assert report["failures"] == []


def test_readiness_report_contains_no_raw_or_sensitive_diagnostic_payload() -> None:
    report = MODULE.build_readiness()
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("rawText", "candidateId", "entityId", "apiKey"):
        assert forbidden not in serialized
    assert "G3.1-B and G3.1-C" in serialized


def test_readiness_fails_when_a_required_binding_is_missing(tmp_path: Path) -> None:
    (tmp_path / "docs/sprint-plans").mkdir(parents=True)
    (tmp_path / "docs/sprint-plans/sprint-12.md").write_text(
        "[x] **S12-R01", encoding="utf-8"
    )
    report = MODULE.build_readiness(tmp_path)
    assert report["measurementGate"]["pass"] is False
    assert report["failures"]
