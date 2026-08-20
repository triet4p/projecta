"""Mocked authorized execution tests for the superseding f11 runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f11_full_stage_a_v2 as runner
from sprint12_pricing import merged_environment
from sprint12_provider_adapter import ProviderAdapterError

AUTHORIZATION = (
    ROOT
    / "evaluation/sprint-12/optimization/"
    "s12-f-11-full-stage-a-authorization.v2.json"
)


class MockTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {
                                "schemaVersion": "relation-evidence-envelope.v1",
                                "extraction": {
                                    "schemaVersion": "m3.v2",
                                    "modelId": "deepseek-v4-flash",
                                    "modelVersion": "mock-v1",
                                    "entities": [],
                                    "relations": [],
                                    "links": [],
                                    "abstentionReason": "no relation evidence",
                                },
                                "relationTriggers": [],
                            }
                        )
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 10,
                "completion_tokens": 5,
            },
        }


def _authorization(
    output_path: Path, package_digest: str, freeze_digest: str
) -> dict[str, object]:
    freeze = runner._load(runner.FULL_FREEZE)
    return {
        "artifactVersion": "s12.s12-f-11.full-stage-a-authorization.test",
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "experimentId": "s12-f-11",
        "providerExecutionAuthorized": True,
        "providerCalls": 48,
        "branchOutputs": 96,
        "requiredSchemaValidResponses": 48,
        "requiredUsageValidResponses": 48,
        "expectedPricedCalls": 48,
        "retryPolicy": "none",
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
        "executionPackage": {
            "path": runner._relative(runner.FULL_PACKAGE),
            "digest": package_digest,
        },
        "freezeRecord": {
            "path": runner._relative(runner.FULL_FREEZE),
            "digest": freeze_digest,
        },
        "commitSha": freeze["commitSha"],
        "providerAdapter": {
            "digest": runner._digest(ROOT / "scripts/sprint12_provider_adapter.py")
        },
        "runtimeConfiguration": {"digest": "PLACEHOLDER_RUNTIME_DIGEST"},
        "outputPath": runner._relative(output_path),
        "costCeilingUsd": "10.00",
    }


def test_mocked_authorized_run_reaches_exactly_48_calls_and_96_branches() -> None:
    output_path = ROOT / "evaluation/sprint-12/optimization/.tmp-f11-v2-report.json"
    authorization_path = ROOT / "evaluation/sprint-12/optimization/.tmp-f11-v2-authorization.json"
    output_path.unlink(missing_ok=True)
    transport = MockTransport()
    adapter = runner.build_adapter(
        {
            "PROJECTA_LLM_TYPE": "openai-response",
            "PROJECTA_LLM_BASE_URL": "https://mock.invalid",
            "PROJECTA_LLM_API_KEY": "mock-only",
            "PROJECTA_LLM_MODEL": "deepseek-v4-flash",
        },
        transport=transport,
    )
    authorization = _authorization(
        output_path,
        runner._digest(runner.FULL_PACKAGE),
        runner._digest(runner.FULL_FREEZE),
    )
    authorization["runtimeConfiguration"] = {
        "digest": adapter.runtime_configuration_digest
    }
    authorization_path.write_text(json.dumps(authorization, indent=2), encoding="utf-8")
    try:
        report = runner.run_full_stage_a(
            provider_adapter=adapter,
            authorization_path=authorization_path,
            output_path=output_path,
        )
        assert len(transport.calls) == 48
        assert report["providerCallCount"] == 48
        assert report["branchOutputCount"] == 96
        assert report["artifactVersion"] == "s12.s12-f-11.full-stage-a-report.v3"
        assert output_path.is_file()
        assert not list(output_path.parent.glob("s12-f-11-stage-a-*.staging.json"))
    finally:
        output_path.unlink(missing_ok=True)
        authorization_path.unlink(missing_ok=True)


def test_v2_adapter_rejects_wrong_model_before_transport_call() -> None:
    transport = MockTransport()
    with pytest.raises(ProviderAdapterError, match="deepseek-v4-flash"):
        runner.build_adapter(
            {
                "PROJECTA_LLM_TYPE": "openai-response",
                "PROJECTA_LLM_BASE_URL": "https://mock.invalid",
                "PROJECTA_LLM_API_KEY": "mock-only",
                "PROJECTA_LLM_MODEL": "other-model",
            },
            transport=transport,
        )
    assert transport.calls == []


def test_issued_authorization_binds_exact_v2_lineage_without_execution() -> None:
    package = runner.validate_full_package(output_path=runner.OUTPUT)
    adapter = runner.build_adapter(merged_environment())
    authorization = runner.validate_authorization(
        package,
        authorization_path=AUTHORIZATION,
        package_path=runner.FULL_PACKAGE,
        output_path=runner.OUTPUT,
        adapter_digest=adapter.adapter_digest,
        runtime_digest=adapter.runtime_configuration_digest,
    )

    assert authorization["providerExecutionAuthorized"] is True
    assert authorization["providerCallsPerformedAtIssuance"] is False
    assert authorization["stageAExecutedAtIssuance"] is False
    assert authorization["providerCalls"] == 48
    assert authorization["branchOutputs"] == 96
    assert authorization["retryAuthorized"] is False
    assert authorization["outputOverwriteAuthorized"] is False
    assert authorization["heldOutAccessAuthorized"] is False
    assert authorization["validationAccessAuthorized"] is False
    assert authorization["stageBAuthorized"] is False
    assert authorization["candidateSelectionAuthorized"] is False
    assert authorization["promotionAuthorized"] is False
    assert not runner.OUTPUT.exists()
