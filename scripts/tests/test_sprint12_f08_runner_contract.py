"""Offline and mocked contracts for the guarded S12-f-08 runner."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
OPT = ROOT / "evaluation/sprint-12/optimization"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps/api/src"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EVALUATOR = load_module("sprint12_evaluator_f08_runner_test", ROOT / "scripts/sprint12_evaluator.py")
PRICING = load_module("sprint12_pricing_f08_runner_test", ROOT / "scripts/sprint12_pricing.py")
RUNNER = load_module(
    "run_sprint12_f08_prompt_experiment_test",
    ROOT / "scripts/run_sprint12_f08_prompt_experiment.py",
)


def read_json(name: str) -> dict:
    return json.loads((OPT / name).read_text(encoding="utf-8"))


def test_runtime_exception_retains_positive_relation_gold_denominator() -> None:
    loaded = EVALUATOR.load_dataset(
        ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json",
        ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v2.json",
        ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json",
    )
    positive = next(case for case in loaded.cases if case["gold"]["relations"])
    subset = replace(loaded, cases=(positive,))

    class RaisingGateway:
        async def extract(self, request):
            raise RuntimeError("synthetic runtime failure")

    case_results, operational, failures, _ = EVALUATOR._runtime_baseline(
        subset,
        {
            "PROJECTA_LLM_TYPE": "openai-response",
            "PROJECTA_LLM_BASE_URL": "https://example.invalid",
            "PROJECTA_LLM_API_KEY": "test-only",
            "PROJECTA_LLM_MODEL": "deepseek-v4-flash",
        },
        gateway_factory=lambda _base_url, _api_key: RaisingGateway(),
        schema_version="m3.v2",
    )

    record = case_results[positive["caseId"]]
    assert record["status"] == "missing-output"
    assert record["relations"]["gold"] == len(positive["gold"]["relations"])
    assert record["relations"]["f1"] == 0.0
    assert record["failureClass"] == "RuntimeError"
    assert failures and operational[0]["promptCacheHitTokens"] == 0


def test_positive_relation_metrics_include_fail_closed_case() -> None:
    metrics = RUNNER.primary_metrics(
        [
            {
                "perCase": {
                    "scored": {
                        "status": "scored",
                        "entities": {"f1": 1.0},
                        "relations": {"f1": 1.0, "gold": 1, "predicted": 1, "truePositive": 1},
                        "abstentionAccuracy": 1.0,
                        "hallucinationRate": 0.0,
                    },
                    "failed": {
                        "status": "missing-output",
                        "relations": {"f1": 0.0, "gold": 1, "predicted": 0, "truePositive": 0},
                    },
                }
            }
        ]
    )
    assert metrics["positiveRelationCaseRuns"] == 2
    assert metrics["positiveRelationMacroF1"] == 0.5
    assert metrics["positiveRelationMicroF1"] == pytest.approx(2 / 3)


def test_pricing_requires_three_cache_aware_token_classes() -> None:
    rates = {
        "inputCacheHitUsdPer1M": "0.0028",
        "inputCacheMissUsdPer1M": "0.14",
        "outputUsdPer1M": "0.28",
    }
    pricing = {"rates": rates}
    assert PRICING.cost_usd(
        {
            "inputTokens": 15,
            "promptCacheHitTokens": 10,
            "promptCacheMissTokens": 5,
            "outputTokens": 3,
        },
        pricing,
    ) == pytest.approx((10 * 0.0028 + 5 * 0.14 + 3 * 0.28) / 1_000_000)
    with pytest.raises(PRICING.PricingBindingError, match="required cache-aware"):
        PRICING.cost_usd(
            {"inputTokens": 15, "outputTokens": 3},
            pricing,
        )


def test_mocked_f08_execution_is_six_interleaved_calls_and_no_overwrite(tmp_path: Path) -> None:
    prereg = read_json("s12-f-08-relation-prompt-preregistration.v1.json")
    case_ids = tuple(prereg["stageA"]["caseIds"])
    pricing = {
        "artifactDigest": "sha256:test-pricing",
        "currency": "USD",
        "unit": "USD per 1M tokens",
        "sourceUrl": "https://example.invalid/pricing",
        "retrievedAt": "2026-08-16",
        "rates": {
            "inputCacheHitUsdPer1M": "0.0028",
            "inputCacheMissUsdPer1M": "0.14",
            "outputUsdPer1M": "0.28",
        },
    }
    calls: list[dict] = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        missing = len(calls) == 2
        per_case = {}
        records = []
        for case_id in kwargs["case_ids"]:
            per_case[case_id] = (
                {
                    "status": "missing-output",
                    "relations": {"f1": 0.0, "gold": 1, "predicted": 0, "truePositive": 0},
                }
                if missing and case_id == kwargs["case_ids"][0]
                else {
                    "status": "scored",
                    "entities": {"f1": 1.0},
                    "relations": {"f1": 1.0, "gold": 1, "predicted": 1, "truePositive": 1},
                    "abstentionAccuracy": 1.0,
                    "hallucinationRate": 0.0,
                }
            )
            records.append(
                {
                    "caseId": case_id,
                    "inputTokens": 15,
                    "promptCacheHitTokens": 10,
                    "promptCacheMissTokens": 5,
                    "outputTokens": 3,
                    "costUsd": 0.0,
                }
            )
        return {
            "status": "RUNTIME_BACKED_WITH_FAILURES" if missing else "RUNTIME_BACKED_SCORED",
            "failureCount": 1 if missing else 0,
            "missingOutputCount": 1 if missing else 0,
            "operational": {"failureCounts": {"missing_output": 1} if missing else {}},
            "operationalRecords": records,
            "metrics": {
                "entityMacroF1": {"f1": 1.0},
                "relationMacroF1": {"f1": 1.0},
                "abstentionAccuracy": 1.0,
                "hallucinationRate": 0.0,
                "linkMacroF1": {"f1": 1.0},
                "perCase": per_case,
            },
            "configuration": {"promptVersion": kwargs["prompt_variant"]},
            "digests": {},
        }

    variants, trace = RUNNER.execute_stage_a(
        prereg, case_ids, pricing, runner=fake_runner, report_dir=tmp_path
    )
    assert len(calls) == 6
    assert [call["prompt_variant"] for call in calls] == [
        "m3.prompt.v3.supersession-guard",
        "m3.prompt.v5.composed-relation-contract",
        "m3.prompt.v5.composed-relation-contract",
        "m3.prompt.v3.supersession-guard",
        "m3.prompt.v3.supersession-guard",
        "m3.prompt.v5.composed-relation-contract",
    ]
    assert [item["arm"] for item in trace] == [
        "control", "candidate", "candidate", "control", "control", "candidate"
    ]
    assert all(tuple(call["case_ids"]) == case_ids for call in calls)
    assert len(list(tmp_path.glob("*.report.v1.json"))) == 6
    assert RUNNER.arm_hard_gate(variants["candidate"]) is False
    with pytest.raises(SystemExit, match="refusing to overwrite run report"):
        RUNNER.execute_stage_a(prereg, case_ids, pricing, runner=fake_runner, report_dir=tmp_path)
