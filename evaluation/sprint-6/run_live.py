"""Opt-in live M4 wording evaluator; network/model variance is not CI acceptance."""

import asyncio
import json
import os
from pathlib import Path

from projecta_api.retrieval.interpreter import interpret
from projecta_api.retrieval.live import OpenAIResponsesAnswerGateway
from projecta_api.retrieval.projection import project
from projecta_api.retrieval.renderer import render


async def evaluate() -> dict[str, object]:
    required = ("PROJECTA_LLM_TYPE", "PROJECTA_LLM_BASE_URL", "PROJECTA_LLM_API_KEY", "PROJECTA_LLM_MODEL")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit("live evaluation disabled; missing required configuration: " + ", ".join(missing))
    root = Path(__file__).parent
    dataset = json.loads((root / "dataset.v1.json").read_text(encoding="utf-8"))
    replay = json.loads((root / "replay_outputs.v1.json").read_text(encoding="utf-8"))
    gateway = OpenAIResponsesAnswerGateway(base_url=os.environ["PROJECTA_LLM_BASE_URL"], api_key=os.environ["PROJECTA_LLM_API_KEY"])
    completed = 0
    failures = 0
    for case in dataset["cases"]:
        try:
            intent = interpret(case["question"])
            payload = replay[intent.query_id]
            answer = render(intent, *project(payload))
            await gateway.answer(case["question"], answer.text, os.environ["PROJECTA_LLM_MODEL"])
            completed += 1
        except Exception:  # noqa: BLE001 - sanitized report only
            failures += 1
    return {"dataset": dataset["version"], "providerType": os.environ["PROJECTA_LLM_TYPE"], "completed": completed, "failures": failures, "factsRemainFixtureVerified": True}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(evaluate()), indent=2, sort_keys=True))
