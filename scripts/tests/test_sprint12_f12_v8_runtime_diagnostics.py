"""Deterministic RM-30 integration tests for the v8 guarded runner."""

from __future__ import annotations

import json
import subprocess
import tempfile
from copy import deepcopy
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import Draft202012Validator

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


class DiagnosticAdapter(MockAdapter):
    """Mock path that reaches both v8 finite diagnostic classifiers."""

    def capture_stage(self, **kwargs: Any) -> ProviderCapture:
        self.calls += 1
        stage = str(kwargs["stage"])
        case_id = str(kwargs["case_id"])
        arm = str(kwargs["arm"])
        if self.calls == 1:
            payload: dict[str, object] = {
                "schemaVersion": "not-bound",
                "entities": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        elif stage == "stage1" and case_id == "s12-a-4003":
            payload = {
                "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
                "entities": [
                    {
                        "candidateId": "entity-01",
                        "type": "Task",
                        "startOffset": 0,
                        "endOffset": 21,
                        "confidence": 1.0,
                    },
                    {
                        "candidateId": "entity-02",
                        "type": "Risk",
                        "startOffset": 29,
                        "endOffset": 43,
                        "confidence": 1.0,
                    },
                ],
                "abstention": {"required": False, "reason": None},
            }
        elif stage == "stage2" and case_id == "s12-a-4003" and arm == "predicted-entities":
            payload = {
                "schemaVersion": "s12-f-12.stage2.relation-envelope.v2",
                "relations": [
                    {
                        "predicate": "answers",
                        "sourceEntityId": "entity-01",
                        "targetEntityId": "entity-02",
                        "confidence": 1.0,
                        "evidence": None,
                        "triggerQuote": "answers",
                    }
                ],
                "abstention": {"required": False, "reason": None},
            }
        elif stage == "stage2":
            payload = {
                "schemaVersion": "s12-f-12.stage2.relation-envelope.v2",
                "relations": [],
                "abstention": {"required": True, "reason": "mock"},
            }
        else:
            payload = {
                "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
                "entities": [],
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


def test_report_schema_closes_raw_payload_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    package = _legacy_fixture()
    monkeypatch.setattr(v8, "validate_preparation_v8", lambda *args, **kwargs: package)
    monkeypatch.setattr(v8, "validate_authorization_v8", lambda *args, **kwargs: {})
    monkeypatch.setattr(v8.v3, "relative", lambda path: Path(path).as_posix())
    report = v8.run_stage_a(
        provider_adapter=MockAdapter(),
        authorization_path=tmp_path / "authorization.json",
        output_path=tmp_path / "report.json",
    )
    schema = json.loads(
        (ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema)
    assert not list(validator.iter_errors(report))
    mutations = (
        ("custody", "rawSourceText"),
        ("configuration", "providerPayload"),
        ("accounting", "rawValidationDetail"),
        ("metrics", "triggerQuote"),
        ("caseRecords", "rawSourceText"),
        ("caseArm", "providerPayload"),
        ("armDiagnostics", "triggerQuote"),
        ("sliceArm", "rawProviderPayload"),
        ("decision", "triggerQuote"),
    )
    for location, field in mutations:
        candidate = deepcopy(report)
        if location in {"caseRecords", "caseArm", "armDiagnostics", "sliceArm"}:
            case = candidate["caseRecords"][0]
            if location == "caseRecords":
                case[field] = "SECRET"
            elif location == "caseArm":
                case["arms"]["predicted-entities"][field] = "SECRET"
            elif location == "armDiagnostics":
                case["arms"]["predicted-entities"]["diagnostics"][field] = "SECRET"
            else:
                candidate["sliceRecords"][0]["metrics"]["arms"]["predicted-entities"][field] = "SECRET"
        else:
            candidate[location][field] = "SECRET"
        assert list(validator.iter_errors(candidate)), (location, field)


def test_report_schema_recursively_closes_forbidden_dynamic_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject raw-data aliases at every report object, including open maps."""

    schema = json.loads(
        (ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema)
    package = _legacy_fixture()

    # The report contains only closed objects except the ontology-keyed maps.
    # Keep this assertion generic so a future open map cannot bypass the key
    # policy by omitting propertyNames.
    open_objects: list[dict[str, object]] = []

    def collect_schema_objects(value: object) -> None:
        if isinstance(value, dict):
            if (
                value.get("type") == "object"
                and "additionalProperties" in value
                and value.get("additionalProperties") is not False
            ):
                open_objects.append(value)
            for child in value.values():
                collect_schema_objects(child)
        elif isinstance(value, list):
            for child in value:
                collect_schema_objects(child)

    collect_schema_objects(schema)
    assert open_objects
    assert all("propertyNames" in value for value in open_objects)

    monkeypatch.setattr(v8, "validate_preparation_v8", lambda *args, **kwargs: package)
    monkeypatch.setattr(v8, "validate_authorization_v8", lambda *args, **kwargs: {})
    monkeypatch.setattr(v8.v3, "relative", lambda path: Path(path).as_posix())

    with tempfile.TemporaryDirectory() as directory:
        report = v8.run_stage_a(
            provider_adapter=MockAdapter(),
            authorization_path=Path(directory) / "authorization.json",
            output_path=Path(directory) / "report.json",
        )

    forbidden = (
        "rawSourceText",
        "providerPayload",
        "rawValidationDetail",
        "triggerQuote",
        "rawPayload",
        "rawEvidenceText",
        "validationMessageWithPayload",
    )
    valid_dynamic_value = {"gold": 0, "predicted": 0, "truePositive": 0, "f1": 0.0}

    def inject_everywhere(value: object, field: str) -> None:
        if isinstance(value, dict):
            children = list(value.values())
            value[field] = deepcopy(valid_dynamic_value)
            for child in children:
                inject_everywhere(child, field)

    for field in forbidden:
        inject_everywhere(report, field)
        try:
            assert list(validator.iter_errors(report)), field
        finally:
            # The next pass must start from the legitimate report.  Every
            # injected key is absent from the generated v8 report.
            def remove_everywhere(value: object) -> None:
                if isinstance(value, dict):
                    value.pop(field, None)
                    for child in value.values():
                        remove_everywhere(child)
                elif isinstance(value, list):
                    for child in value:
                        remove_everywhere(child)

            remove_everywhere(report)

    assert not list(validator.iter_errors(report))

    # Explicit regression probes for the original RM33 bypasses.
    probes = (
        (report["metrics"]["arms"]["predicted-entities"]["entity"]["byType"], "rawSourceText"),
        (report["metrics"]["arms"]["predicted-entities"]["relation"]["semantic"]["byPredicate"], "providerPayload"),
        (report["caseRecords"][0]["arms"]["predicted-entities"]["entity"]["byType"], "rawValidationDetail"),
        (report["caseRecords"][0]["arms"]["predicted-entities"]["relation"]["semantic"]["byPredicate"], "triggerQuote"),
    )
    for mapping, field in probes:
        mapping[field] = deepcopy(valid_dynamic_value)
        try:
            assert list(validator.iter_errors(report)), field
        finally:
            del mapping[field]

    assert not list(validator.iter_errors(report))


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


def test_all_valid_mock_has_zero_diagnostic_totals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package = _legacy_fixture()
    adapter = MockAdapter()
    monkeypatch.setattr(v8, "validate_preparation_v8", lambda *args, **kwargs: package)
    monkeypatch.setattr(v8, "validate_authorization_v8", lambda *args, **kwargs: {})
    monkeypatch.setattr(v8.v3, "relative", lambda path: Path(path).as_posix())
    report = v8.run_stage_a(
        provider_adapter=adapter,
        authorization_path=tmp_path / "authorization.json",
        output_path=tmp_path / "report.json",
    )
    assert report["metrics"]["hardGates"]["schemaInvalid"] == 0
    assert report["metrics"]["hardGates"]["invalidEvidence"] == 0
    assert report["diagnostics"]["schemaFailureTotal"] == 0
    assert report["diagnostics"]["evidenceFailureTotal"] == 0


def test_mock_path_invokes_both_classifiers_and_reconciles_exact_totals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    package = _legacy_fixture()
    adapter = DiagnosticAdapter()
    calls: Counter[str] = Counter()
    original_schema = v8.classify_schema_failure
    original_evidence = v8.diagnose_evidence_failure

    def classify(*args: Any, **kwargs: Any) -> Any:
        calls["schema"] += 1
        return original_schema(*args, **kwargs)

    def diagnose(*args: Any, **kwargs: Any) -> Any:
        calls["evidence"] += 1
        return original_evidence(*args, **kwargs)

    monkeypatch.setattr(v8, "classify_schema_failure", classify)
    monkeypatch.setattr(v8, "diagnose_evidence_failure", diagnose)
    monkeypatch.setattr(v8, "validate_preparation_v8", lambda *args, **kwargs: package)
    monkeypatch.setattr(v8, "validate_authorization_v8", lambda *args, **kwargs: {})
    monkeypatch.setattr(v8.v3, "relative", lambda path: Path(path).as_posix())
    report = v8.run_stage_a(
        provider_adapter=adapter,
        authorization_path=tmp_path / "authorization.json",
        output_path=tmp_path / "report.json",
    )
    assert calls["schema"] >= 1
    assert calls["evidence"] >= 1
    assert report["diagnostics"]["schemaFailureTotal"] == report["metrics"]["hardGates"]["schemaInvalid"]
    assert report["diagnostics"]["schemaFailureTotal"] >= 1
    assert report["diagnostics"]["evidenceFailureTotal"] == report["metrics"]["hardGates"]["invalidEvidence"]
    assert report["diagnostics"]["schemaFailureTotal"] == report["metrics"]["hardGates"]["schemaInvalid"]
    assert report["diagnostics"]["evidenceReasonCounts"]["predicted-entities"]["evidence_span_missing"] >= 1


def test_current_rm32_package_runs_mocked_144_call_path_without_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    output = ROOT / "evaluation/sprint-12/optimization/.s12-f-12-v8-mock-report.json"
    output.unlink(missing_ok=True)
    monkeypatch.setattr(v8, "validate_authorization_v8", lambda *args, **kwargs: {})
    adapter = MockAdapter(malformed_first=True)
    try:
        report = v8.run_stage_a(
            provider_adapter=adapter,
            authorization_path=ROOT / "evaluation/sprint-12/optimization/.mock-authorization.json",
            output_path=output,
        )
        assert adapter.calls == 144
        assert report["accounting"]["providerCallsAttempted"] == 144
        assert report["accounting"]["retryCount"] == 0
        assert report["diagnostics"]["reasonCountsReconciled"] is True
    finally:
        output.unlink(missing_ok=True)
