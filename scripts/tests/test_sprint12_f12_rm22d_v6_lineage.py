from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-issuance-draft.v6.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-execution-package.v6.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-technical-freeze.v6.json"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_v5_historical_scope_is_unchanged() -> None:
    historical = load(
        ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-issuance-draft.v5.json"
    )
    assert historical["preparationScope"] == "S12-RM-22C"


def test_v6_scope_is_exact_across_lineage() -> None:
    assert all(
        load(path)["preparationScope"] == "S12-RM-22D"
        for path in (PREREG, PACKAGE, FREEZE)
    )


def test_v6_keeps_execution_commit_and_rebinds_digests() -> None:
    prereg = load(PREREG)
    package = load(PACKAGE)
    freeze = load(FREEZE)
    commit = "b63ebcb4603cd2cabeb796a38c86be4471304f3f"
    assert prereg["executionCommitSha"] == commit
    assert package["commitSha"] == commit
    assert freeze["commitSha"] == commit
    assert freeze["preregistrationDigest"] == digest(PREREG)
    assert freeze["executionPackageDigest"] == digest(PACKAGE)


def test_v6_preflight_binding_is_rebound() -> None:
    package = load(PACKAGE)
    preflight = package["preflight"]
    assert preflight["path"] == "scripts/preflight_sprint12_f12_rm22d_v6.py"
    assert preflight["digest"] == digest(ROOT / str(preflight["path"]))
    assert package["boundDigests"][preflight["path"]] == preflight["digest"]


def test_v6_preflight_is_zero_call_ready() -> None:
    pytest.importorskip("jsonschema")
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import preflight_sprint12_f12_rm22d_v6 as preflight

    result = preflight.run_preflight()
    assert result["status"] == "F12_RM22D_READY_ZERO_CALL_V6"
    assert result["providerCalls"] == 0
    assert result["preparationScope"] == "S12-RM-22D"
