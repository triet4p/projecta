"""M4 read-only orchestration over the finite Semantic Core client."""

import logging
from time import perf_counter
from typing import Protocol

from projecta_api.context import TrustedRequestContext
from projecta_api.retrieval.contracts import Answer
from projecta_api.retrieval.errors import RetrievalError, RetrievalErrorCode
from projecta_api.retrieval.interpreter import interpret
from projecta_api.retrieval.projection import project
from projecta_api.retrieval.renderer import render
from projecta_api.retrieval.telemetry import RetrievalTelemetry


class RetrievalCore(Protocol):
    async def request(
        self, context: TrustedRequestContext, method: str, path: str, body: object | None = None
    ) -> object: ...


class RetrievalService:
    """Interpret, retrieve, project, verify, and render without mutation."""

    def __init__(self, semantic_client: RetrievalCore) -> None:
        self._client = semantic_client
        self._logger = logging.getLogger("projecta.retrieval")

    async def answer(self, context: TrustedRequestContext, question: str, limit: int = 50) -> Answer:
        started = perf_counter()
        query_id = "unknown"
        try:
            query = interpret(question, limit=limit)
            query_id = query.query_id
            path = "/v1/retrieval/" + query.query_id + "?limit=" + str(query.parameters["limit"])
            if query.query_id == "requirement-history":
                path += "&requirementId=" + str(query.parameters["requirementId"])
            payload = await self._client.request(context, "GET", path, {"parameters": query.parameters})
            facts, citations, meta = project(payload)
            answer = render(query, facts, citations, meta)
            elapsed_ms = int((perf_counter() - started) * 1000)
            self._logger.info("m4_retrieval_completed", extra={"projecta_retrieval": self.telemetry(answer, elapsed_ms).as_dict()})
            return answer
        except Exception as error:
            elapsed_ms = int((perf_counter() - started) * 1000)
            self._logger.info("m4_retrieval_failed", extra={"projecta_retrieval": RetrievalTelemetry(
                "m4.v1", query_id, elapsed_ms, 0, 0, (), False, _error_class(error)).as_dict()})
            raise

    @staticmethod
    def telemetry(answer: Answer, elapsed_ms: int) -> RetrievalTelemetry:
        return RetrievalTelemetry(
            "m4.v1", answer.query.query_id, elapsed_ms, len(answer.facts),
            len(answer.citations), tuple(sorted({fact.status for fact in answer.facts})),
            answer.abstained,
        )


def _error_class(error: Exception) -> str:
    if isinstance(error, RetrievalError):
        return error.code.value
    if isinstance(error, TimeoutError):
        return RetrievalErrorCode.TIMEOUT.value
    downstream_code = getattr(error, "code", None)
    if isinstance(downstream_code, str) and downstream_code:
        return downstream_code.lower()
    return RetrievalErrorCode.UNAVAILABLE_DEPENDENCY.value
