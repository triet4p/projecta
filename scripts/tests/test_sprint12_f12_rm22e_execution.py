from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v6 as v6
from sprint12_provider_adapter import ProviderCapture


class MockStageAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def capture_stage(self, **kwargs: object) -> ProviderCapture:
        self.calls.append(kwargs)
        if kwargs["stage"] == "stage1":
            payload = {
                "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
                "entities": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        else:
            payload = {
                "schemaVersion": "s12-f-12.stage2.relation-envelope.v2",
                "relations": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        return ProviderCapture(
            payload=payload,
            usage={
                "inputTokens": 1000,
                "promptCacheHitTokens": 0,
                "promptCacheMissTokens": 1000,
                "outputTokens": 100,
            },
            retry_count=0,
        )


def _authorization(path: Path) -> Path:
    package = json.loads(v6.PACKAGE.read_text(encoding="utf-8"))
    freeze = json.loads(v6.FREEZE.read_text(encoding="utf-8"))
    # Mock authorization belongs beside the temporary output, never beside the
    # tracked immutable v6 report.
    target = path.with_name("rm22e-test-authorization.json")
    payload = {
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "experimentId": "s12-f-12",
        "providerExecutionAuthorized": True,
        "providerCalls": 144,
        "retryPolicy": "none",
        "commitSha": package["commitSha"],
        "executionPackage": {"digest": v6.digest(v6.PACKAGE)},
        "freezeRecord": {"digest": v6.digest(v6.FREEZE)},
        "outputPath": path.name,
        "costCeilingUsd": "10.00",
        "heldOutInspected": False,
        "heldOutAccessAuthorized": False,
        "validationAccessAuthorized": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
    }
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert freeze["commitSha"] == package["commitSha"]
    return target


def test_v7_unauthorized_path_has_zero_calls(tmp_path: Path) -> None:
    adapter = MockStageAdapter()
    output = tmp_path / "rm22e-unauthorized-report.json"
    with pytest.raises(RuntimeError, match="authorization|digest|commit"):
        v6.run_stage_a(
            provider_adapter=adapter,
            authorization_path=None,
            output_path=output,
        )
    assert len(adapter.calls) == 0


def test_archived_v6_lineage_rejects_current_execution_before_capture(tmp_path: Path) -> None:
    output = tmp_path / "rm22e-authorized-report.json"
    authorization = _authorization(output)
    adapter = MockStageAdapter()
    with pytest.raises(RuntimeError, match="digest|commit|authorization"):
        v6.run_stage_a(
            provider_adapter=adapter,
            authorization_path=authorization,
            output_path=output,
        )
    assert adapter.calls == []
    assert not output.exists()


def test_archived_v6_lineage_replay_attempts_fail_closed_without_capture(tmp_path: Path) -> None:
    output = tmp_path / "rm22e-replay-report.json"
    authorization = _authorization(output)
    first_adapter = MockStageAdapter()
    second_adapter = MockStageAdapter()
    with pytest.raises(RuntimeError, match="digest|commit|authorization"):
        v6.run_stage_a(
            provider_adapter=first_adapter,
            authorization_path=authorization,
            output_path=output,
        )
    with pytest.raises(RuntimeError, match="digest|commit|authorization"):
        v6.run_stage_a(
            provider_adapter=second_adapter,
            authorization_path=authorization,
            output_path=output,
        )
    assert len(first_adapter.calls) == 0
    assert len(second_adapter.calls) == 0


def test_archived_v6_default_output_is_immutable_and_rejects_attempt() -> None:
    before = v6.digest(v6.OUTPUT)
    assert before == "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
    adapter = MockStageAdapter()
    with pytest.raises(RuntimeError, match="output|authorization|digest|commit"):
        v6.run_stage_a(
            provider_adapter=adapter,
            authorization_path=None,
            output_path=v6.OUTPUT,
        )
    assert adapter.calls == []
    assert v6.digest(v6.OUTPUT) == before
