"""Deterministic RM-30 integration tests for the v8 guarded runner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import run_sprint12_f12_stage_a_v8 as v8
from sprint12_provider_adapter import ProviderCapture


ROOT = Path(__file__).resolve().parents[2]


def _legacy_fixture() -> dict[str, Any]:
    package = json.loads(
        (ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json").read_text(encoding="utf-8")
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    package.update(
        {
            "status": "EXECUTION_PACKAGE_PREPARED_PENDING_RM23B_OWNER_REVIEW",
            "commitSha": commit,
            "providerCalls": 144,
            "relationBranchOutputs": 96,
            "runtimeConfiguration": {
                "digest": "sha256:" + "0" * 64,
            },
            "prompt": {"digest": "sha256:" + "1" * 64},
            "stageSchemas": {
                "stage1": {"digest": "sha256:" + "2" * 64},
                "stage2": {"digest": "sha256:" + "3" * 64},
            },
        }
    )
    return package


class MockAdapter:
    def __init__(self, *, malformed_first: bool = False) -> None:
        self.calls = 0
        self.malformed_first = malformed_first

    def capture_stage(self, **kwargs: Any) -> ProviderCapture:
        self.calls += 1
        stage = str(kwargs["stage"])
        if self.malformed_first and self.calls == 1:
            payload: dict[str, object] = {
                "schemaVersion": "not-bound",
                "entities": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        elif stage == "stage1":
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
                "promptCacheHitTokens": 0,
                "promptCacheMissTokens": 1,
                "outputTokens": 1,
            },
            retry_count=0,
        )


def test_malformed_evidence_is_finite_and_fail_closed() -> None:
    malformed = SimpleNamespace(
        trigger_quote="ok",
        evidence_start="bad",
        evidence_end=3,
    )
    reason = v8.diagnose_evidence_failure(
        malformed,
        context=SimpleNamespace(
            source_text="okay",
            source_length=4,
            source_digest="sha256:bad",
            sentence=None,
            clause=(0, 4),
            trigger_occurrences=(),
        ),
        endpoint_spans=((0, 1), (2, 3)),
    )
    assert reason is not None
    assert reason.code == "materializer_detail_unavailable"
    assert reason.detailAvailable is False
    assert set(reason.as_dict()) == {"code", "detailAvailable"}


def test_report_schema_rejects_unregistered_reason() -> None:
    schema = json.loads(
        (ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json").read_text(encoding="utf-8")
    )
    invalid = {
        "artifactVersion": "s12-f-12.stage-a-report.v8",
        "experimentId": "s12-f-12",
        "custody": {},
        "configuration": {},
        "accounting": {},
        "metrics": {},
        "caseRecords": [],
        "sliceRecords": [],
        "decision": {},
        "diagnostics": {
            "schemaReasonCounts": {
                arm: {code: 0 for code in v8.SCHEMA_REASON_CODES}
                for arm in ("predicted-entities", "gold-entities", "gold-relations")
            },
            "evidenceReasonCounts": {
                arm: {code: 0 for code in v8.EVIDENCE_REASON_CODES}
                for arm in ("predicted-entities", "gold-entities", "gold-relations")
            },
            "schemaFailureTotal": 0,
            "evidenceFailureTotal": 0,
            "reasonCountsReconciled": True,
            "rawDataPolicy": {
                "rawSourceTextIncluded": False,
                "rawProviderPayloadIncluded": False,
                "rawValidationDetailIncluded": False,
                "rawTriggerQuoteIncluded": False,
            },
        },
    }
    invalid["diagnostics"]["schemaReasonCounts"]["predicted-entities"]["unknown_not_registered"] = 1
    from jsonschema import Draft202012Validator

    errors = list(Draft202012Validator(schema).iter_errors(invalid))
    assert errors


def test_guarded_runtime_unauthorized_makes_zero_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package = _legacy_fixture()
    adapter = MockAdapter()
    monkeypatch.setattr(v8, "validate_preparation_v8", lambda *args, **kwargs: package)
    monkeypatch.setattr(v8, "validate_authorization_v8", lambda *args, **kwargs: {})
    monkeypatch.setattr(v8.v3, "relative", lambda path: Path(path).as_posix())
    with pytest.raises(v8.v3.F12StageAV3Error):
        v8.run_stage_a(provider_adapter=adapter, authorization_path=None, output_path=tmp_path / "report.json")
    assert adapter.calls == 0


def test_guarded_runtime_mock_runs_144_calls_and_persists_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package = _legacy_fixture()
    adapter = MockAdapter(malformed_first=True)
    monkeypatch.setattr(v8, "validate_preparation_v8", lambda *args, **kwargs: package)
    monkeypatch.setattr(v8, "validate_authorization_v8", lambda *args, **kwargs: {})
    monkeypatch.setattr(v8.v3, "relative", lambda path: Path(path).as_posix())
    output = tmp_path / "report.json"
    report = v8.run_stage_a(
        provider_adapter=adapter,
        authorization_path=tmp_path / "authorization.json",
        output_path=output,
    )
    assert adapter.calls == 144
    assert report["artifactVersion"] == "s12-f-12.stage-a-report.v8"
    assert report["diagnostics"]["reasonCountsReconciled"] is True
    assert report["diagnostics"]["schemaFailureTotal"] >= 1
    assert report["diagnostics"]["rawDataPolicy"]["rawProviderPayloadIncluded"] is False
    assert output.exists()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == report
    with pytest.raises(v8.v3.F12StageAV3Error):
        v8.run_stage_a(
            provider_adapter=MockAdapter(),
            authorization_path=tmp_path / "authorization.json",
            output_path=output,
        )
