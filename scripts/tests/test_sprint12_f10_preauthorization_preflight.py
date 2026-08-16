"""Contract tests for the final S12-f-10 preauthorization preflight."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "apps" / "api" / "src")]

from preflight_sprint12_f10_preauthorization import build_preflight
from run_sprint12_next_tool_experiment import (
    ExecutionPackageError,
    run_offline_stage_a,
    validate_final_execution_package,
)
from sprint12_provider_adapter import CallableProviderAdapter, ProviderCapture


def test_final_package_is_implemented_but_commit_binding_keeps_preflight_closed() -> None:
    package = validate_final_execution_package()
    assert package["executionRunnerImplemented"] is True
    report = build_preflight(run_tests=False)
    assert report["status"] == "NO_GO_PREAUTHORIZATION_PREFLIGHT"
    assert report["checks"]["packageStatus"] is True
    assert report["checks"]["providerSchemasMatch"] is True
    assert report["checks"]["caseSelectionReproducible"] is True
    assert report["checks"]["commitPresentInHead"] is True
    assert report["checks"]["allBoundFilesInCommit"] is True
    assert report["checks"]["canonicalTestsPass"] is False
    assert report["providerExecutionAuthorized"] is False


def test_offline_runner_uses_48_captures_and_96_sanitized_branches(tmp_path: Path) -> None:
    payload = {
        "schemaVersion": "relation-evidence-envelope.v1",
        "extraction": {
            "schemaVersion": "m3.v2",
            "modelId": "offline",
            "modelVersion": "test",
            "entities": [],
            "relations": [],
            "links": [],
            "abstentionReason": "offline",
            "usage": {
                "inputTokens": 0,
                "promptCacheHitTokens": 0,
                "promptCacheMissTokens": 0,
                "outputTokens": 0,
            },
        },
        "relationTriggers": [],
    }
    calls: list[str] = []
    adapter = CallableProviderAdapter(
        lambda **kwargs: calls.append(str(kwargs["case_id"]))
        or ProviderCapture(
            payload=payload,
            usage={
                "inputTokens": 0,
                "promptCacheHitTokens": 0,
                "promptCacheMissTokens": 0,
                "outputTokens": 0,
            },
        )
    )
    output = tmp_path / "stage-a-report.json"
    report = run_offline_stage_a(provider_adapter=adapter, output_path=output)

    assert len(calls) == 48
    assert report["providerCallCount"] == 48
    assert report["branchOutputCount"] == 96
    assert report["rawSensitiveDataIncluded"] is False
    assert output.exists()
    try:
        run_offline_stage_a(provider_adapter=adapter, output_path=output)
    except ExecutionPackageError as error:
        assert "overwrite" in str(error)
    else:
        raise AssertionError("runner must refuse to overwrite a sanitized report")
