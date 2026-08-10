"""Provider-neutral live answer quality adapter; provider text never supplies facts."""

import json
from typing import Protocol

from openai import AsyncOpenAI


class AnswerGateway(Protocol):
    async def answer(self, question: str, verified_context: str, model: str) -> str: ...


class OpenAIResponsesAnswerGateway:
    """OpenAI-compatible Responses adapter for opt-in wording evaluation only."""

    def __init__(self, *, base_url: str, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=0)

    async def answer(self, question: str, verified_context: str, model: str) -> str:
        response = await self._client.responses.create(
            model=model,
            instructions="Render only the supplied verified context. Never add facts or citations.",
            input=json.dumps({"question": question, "verifiedContext": verified_context}),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "m4_live_answer",
                    "schema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            },
            timeout=60.0,
        )
        output = getattr(response, "output_text", None)
        if not isinstance(output, str) or not output:
            raise RuntimeError("provider returned no answer")
        return output
