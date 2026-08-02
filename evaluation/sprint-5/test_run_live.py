"""Live evaluation fails closed when required configuration is absent."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import run_live  # noqa: E402

from projecta_api.extraction.contracts import ExtractionResponse  # noqa: E402
from projecta_api.llm.gateway import GatewayResponse, NormalizedGatewayError  # noqa: E402


@pytest.mark.skipif(
    Path(__file__).parents[2].joinpath(".env").is_file(),
    reason="a local .env supplies live LLM configuration; run without .env to verify fail-closed",
)
def test_live_runner_fails_without_required_configuration() -> None:
    env = os.environ.copy()
    for name in ("PROJECTA_LLM_TYPE", "PROJECTA_LLM_BASE_URL", "PROJECTA_LLM_API_KEY"):
        env.pop(name, None)
    env.pop("PROJECTA_LLM_MODEL", None)
    result = subprocess.run(
        [sys.executable, "evaluation/sprint-5/run_live.py"],
        cwd=Path(__file__).parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["error"] == "missing_required_llm_configuration"


def test_live_runner_retries_invalid_evidence_once(monkeypatch, capsys) -> None:
    _set_llm_environment(monkeypatch)
    monkeypatch.setenv("PROJECTA_LIVE_CASE_ID", "empty-001")
    calls = {"extract": 0, "normalize": 0}

    class FakeGateway:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def extract(self, request: object) -> GatewayResponse:
            calls["extract"] += 1
            return GatewayResponse(
                extraction=ExtractionResponse(
                    schemaVersion="m3.v1",
                    modelId="fake-model",
                    modelVersion="v1",
                    abstentionReason="no supported proposal",
                )
            )

    def fake_normalize(raw_text: str, response: ExtractionResponse, bounded_entities: object) -> ExtractionResponse:
        calls["normalize"] += 1
        if calls["normalize"] == 1:
            raise NormalizedGatewayError("invalid_evidence", "evidence does not match", retryable=False)
        return response

    monkeypatch.setattr(run_live, "OpenAIResponsesGateway", FakeGateway)
    monkeypatch.setattr(run_live, "normalize_extraction", fake_normalize)

    code = asyncio.run(run_live.run())
    assert code == 0
    assert calls["extract"] == 2
    assert json.loads(capsys.readouterr().out)["status"] == "completed"


def test_live_runner_reports_persistent_invalid_evidence(monkeypatch, capsys) -> None:
    _set_llm_environment(monkeypatch)
    monkeypatch.setenv("PROJECTA_LIVE_CASE_ID", "empty-001")
    calls = {"extract": 0, "normalize": 0}

    class FakeGateway:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def extract(self, request: object) -> GatewayResponse:
            calls["extract"] += 1
            return GatewayResponse(
                extraction=ExtractionResponse(
                    schemaVersion="m3.v1",
                    modelId="fake-model",
                    modelVersion="v1",
                    abstentionReason="no supported proposal",
                )
            )

    def fake_normalize(raw_text: str, response: ExtractionResponse, bounded_entities: object) -> ExtractionResponse:
        calls["normalize"] += 1
        raise NormalizedGatewayError("invalid_evidence", "evidence does not match", retryable=False)

    monkeypatch.setattr(run_live, "OpenAIResponsesGateway", FakeGateway)
    monkeypatch.setattr(run_live, "normalize_extraction", fake_normalize)

    code = asyncio.run(run_live.run())
    assert code == 1
    assert calls["extract"] == 2
    report = json.loads(capsys.readouterr().out)
    assert report["errorClasses"]["empty-001"]["errorClass"] == "invalid_evidence"


def _set_llm_environment(monkeypatch) -> None:
    monkeypatch.setenv("PROJECTA_LLM_TYPE", "openai-response")
    monkeypatch.setenv("PROJECTA_LLM_BASE_URL", "http://fake.invalid")
    monkeypatch.setenv("PROJECTA_LLM_API_KEY", "fake-key")
    monkeypatch.setenv("PROJECTA_LLM_MODEL", "fake-model")
