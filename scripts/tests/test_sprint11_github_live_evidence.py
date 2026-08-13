"""Regression tests for provenance and exact-delta live evidence validation."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR_PATH = ROOT / "scripts/check_sprint11_github_live_evidence.py"
_SPEC = importlib.util.spec_from_file_location("sprint11_live_evidence_validator", _VALIDATOR_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_validate = _MODULE._validate
_journey_waiver_applies = _MODULE._journey_waiver_applies


def _artifact(name: str) -> dict[str, object]:
    return json.loads(
        (ROOT / "docs/sprint-plans/sprint-11/artifacts" / name).read_text(encoding="utf-8")
    )


def test_run_digest_tampering_breaks_provenance_binding() -> None:
    record = _artifact("s11-A18-github-live-acceptance.json")
    tampered = copy.deepcopy(record)
    tampered["baselineRun"]["runDigest"] = "0" * 64  # type: ignore[index]
    errors = _validate(tampered, journey=False)
    assert any("provenance digest" in error for error in errors)


def test_continuity_delta_tampering_breaks_exact_run_binding() -> None:
    record = _artifact("s11-A18-github-live-acceptance.json")
    tampered = copy.deepcopy(record)
    tampered["continuity"]["candidateDeltaCount"] = 3  # type: ignore[index]
    errors = _validate(tampered, journey=False)
    assert any("exactly the imported event count" in error for error in errors)


def test_edit_snapshot_digest_tampering_breaks_revision_proof() -> None:
    record = _artifact("s11-A18-github-live-journey.json")
    tampered = copy.deepcopy(record)
    before = copy.deepcopy(tampered["providerSnapshot"])
    before["expectedEventCount"] += 2  # type: ignore[operator]
    before["recordCount"] += 2  # type: ignore[operator]
    after = copy.deepcopy(before)
    tampered["beforeEditSnapshot"] = before
    tampered["afterEditSnapshot"] = after
    tampered["afterEditSnapshot"]["recordDigest"] = tampered["beforeEditSnapshot"]["recordDigest"]  # type: ignore[index]
    errors = _validate(tampered, journey=True)
    assert any("content/revision change" in error for error in errors)


def test_g2_waiver_accepts_only_the_bound_failed_journey() -> None:
    record = _artifact("s11-A18-github-live-journey.json")
    assert _journey_waiver_applies(record)

    tampered = copy.deepcopy(record)
    tampered["repositoryHash"] = "0" * 64
    assert not _journey_waiver_applies(tampered)
