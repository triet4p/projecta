"""Credential-free M4 interpretation, retrieval, and grounding evaluator."""

import json
from pathlib import Path

from projecta_api.retrieval.errors import RetrievalError, RetrievalErrorCode
from projecta_api.retrieval.interpreter import interpret
from projecta_api.retrieval.projection import project
from projecta_api.retrieval.renderer import render


def main() -> int:
    root = Path(__file__).parent
    dataset = json.loads((root / "dataset.v1.json").read_text(encoding="utf-8"))
    replay = json.loads((root / "replay_outputs.v1.json").read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    for case in dataset["cases"]:
        expected_intent = case["intent"]
        try:
            intent = interpret(case["question"])
            payload = replay.get(intent.query_id)
            if case["expectedCount"] == 0:
                payload = {"items": [], "meta": {"projectionVersion": "m4.v1", "sourceRevision": "replay-r1", "asOf": "2026-08-04T00:00:00Z", "partial": False, "stale": False}}
            if payload is None:
                raise RetrievalError(RetrievalErrorCode.UNKNOWN_INTENT)
            facts, citations, meta = project(payload)
            answer = render(intent, facts, citations, meta)
            expected_empty = case["expectedCount"] == 0
            grounded = bool(answer.facts) and all(fact.citation_ids for fact in answer.facts)
            passed = expected_intent == intent.query_id and len(answer.facts) == case["expectedCount"] and (answer.abstained if expected_empty else not answer.abstained and grounded)
            result = {"id": case["id"], "intent": intent.query_id, "facts": len(answer.facts), "citations": len(answer.citations), "grounded": grounded, "abstained": answer.abstained, "passed": passed}
        except RetrievalError as error:
            passed = expected_intent in {"ambiguous", "cross-project"}
            result = {"id": case["id"], "intent": expected_intent, "facts": 0, "citations": 0, "grounded": False, "error": error.code.value, "passed": passed}
        results.append(result)
    passed_count = sum(bool(result["passed"]) for result in results)
    evaluated = [result for result in results if result["intent"] not in {"ambiguous", "cross-project"}]
    grounded = sum(bool(result["grounded"]) for result in evaluated)
    report = {"dataset": dataset["version"], "cases": len(results), "passed": passed_count, "intentAccuracy": passed_count / len(results), "groundingRate": grounded / max(1, len(evaluated)), "abstentions": sum(bool(result.get("abstained")) for result in results), "results": results}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
