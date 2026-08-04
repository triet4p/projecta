"""M4 deterministic interpretation, grounding, and redaction tests."""

import logging
from datetime import UTC, datetime

import pytest

from projecta_api.context import TrustedRequestContext
from projecta_api.retrieval.contracts import Fact, ProjectionMeta
from projecta_api.retrieval.errors import RetrievalError, RetrievalErrorCode
from projecta_api.retrieval.interpreter import interpret
from projecta_api.retrieval.renderer import render
from projecta_api.retrieval.service import RetrievalService


def test_interpreter_is_bounded_and_typed() -> None:
    assert interpret("What are the current requirements?").query_id == "current-requirements"
    result = interpret("What changed in requirement req-address?")
    assert result.query_id == "requirement-history"
    assert result.parameters["requirementId"] == "req-address"
    with pytest.raises(RetrievalError) as error:
        interpret("Tell me everything")
    assert error.value.code == RetrievalErrorCode.UNKNOWN_INTENT


def test_renderer_rejects_unsupported_citation() -> None:
    query = interpret("What are the current requirements?")
    fact = Fact(id="req-1", type="Requirement", label="Use MFA", status="asserted", citationIds=["missing"])
    with pytest.raises(RetrievalError) as error:
        render(query, [fact], [], ProjectionMeta(sourceRevision="r1", asOf=datetime.now(UTC)))
    assert error.value.code == RetrievalErrorCode.NO_EVIDENCE


def test_renderer_abstains_when_no_evidence_exists() -> None:
    query = interpret("What are the current requirements?")
    answer = render(query, [], [], ProjectionMeta(sourceRevision="r1", asOf=datetime.now(UTC)))
    assert answer.complete is False
    assert answer.abstained is True
    assert answer.warnings == ["no_evidence"]


class FakeCore:
    async def request(self, context: TrustedRequestContext, method: str, path: str, body: object) -> object:
        assert method == "GET"
        assert path == "/v1/retrieval/current-requirements?limit=50"
        assert context.project_id == "checkout"
        return {
            "items": [{
                "id": "req-1", "type": "Requirement", "label": "Use MFA", "status": "asserted",
                "citation": {"id": "cite-1", "sourceId": "note-1", "evidenceText": "Use MFA", "startOffset": 0, "endOffset": 7},
            }],
            "meta": {"sourceRevision": "r1", "asOf": "2026-08-04T00:00:00Z"},
        }


class FailingCore:
    async def request(self, context: TrustedRequestContext, method: str, path: str, body: object) -> object:
        raise TimeoutError("provider timeout")


@pytest.mark.asyncio
async def test_service_returns_grounded_read_only_answer() -> None:
    answer = await RetrievalService(FakeCore()).answer(
        TrustedRequestContext("checkout", "le", "request-1"), "What are the current requirements?"
    )
    assert answer.facts[0].status == "asserted"
    assert answer.citations[0].source_id == "note-1"
    assert answer.answer_version == "m4.v1"


@pytest.mark.asyncio
async def test_service_emits_failure_telemetry(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="projecta.retrieval")
    with pytest.raises(TimeoutError):
        await RetrievalService(FailingCore()).answer(
            TrustedRequestContext("checkout", "le", "request-1"), "What are the current requirements?"
        )
    telemetry = next(record.projecta_retrieval for record in caplog.records if record.message == "m4_retrieval_failed")
    assert telemetry["errorClass"] == "timeout"


@pytest.mark.asyncio
async def test_service_emits_retrieval_taxonomy_for_interpretation_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="projecta.retrieval")
    with pytest.raises(RetrievalError):
        await RetrievalService(FakeCore()).answer(
            TrustedRequestContext("checkout", "le", "request-1"), "Tell me everything"
        )
    telemetry = next(
        record.projecta_retrieval
        for record in caplog.records
        if record.message == "m4_retrieval_failed"
    )
    assert telemetry["queryId"] == "unknown"
    assert telemetry["errorClass"] == "unknown_intent"
