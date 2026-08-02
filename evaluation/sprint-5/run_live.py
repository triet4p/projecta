"""Opt-in live DeepSeek/OpenAI-compatible evaluation.

Canonical CI must use ``run_offline.py``. This command is intentionally a
separate, credential-gated path and emits aggregate metadata only.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "apps" / "api" / "src"))

from metrics_runner import evaluate
from pydantic import ValidationError

from projecta_api.config import Settings
from projecta_api.extraction.normalize import normalize_extraction
from projecta_api.extraction.prompt import build_extraction_prompt
from projecta_api.extraction.service import _response_schema
from projecta_api.llm.gateway import GatewayRequest, NormalizedGatewayError
from projecta_api.llm.openai_responses import OpenAIResponsesGateway
from projecta_api.llm.resilience import ResilientGateway


async def run() -> int:
    try:
        settings = Settings()
    except ValidationError as error:
        variables = sorted({str(item["loc"][0]) for item in error.errors() if str(item["loc"][0]).startswith("PROJECTA_LLM_")})
        print(json.dumps({"status": "failed", "error": "missing_required_llm_configuration", "variables": variables}, sort_keys=True))
        return 1
    if settings.llm_type not in {"openai-response", "openai"}:
        print(json.dumps({"status": "failed", "error": "unsupported_llm_type", "value": settings.llm_type}, sort_keys=True))
        return 1
    gateway = ResilientGateway(OpenAIResponsesGateway(base_url=str(settings.llm_base_url), api_key=settings.llm_api_key.get_secret_value()), max_retries=1)
    dataset = json.loads((Path(__file__).parent / "dataset.v1.json").read_text(encoding="utf-8"))
    requested_case = os.environ.get("PROJECTA_LIVE_CASE_ID")
    cases = [case for case in dataset["cases"] if not requested_case or case["id"] == requested_case]
    completed = 0
    failures: dict[str, dict[str, object]] = {}
    outputs: dict[str, dict[str, object]] = {}
    for case in cases:
        system, user = build_extraction_prompt(
            case["rawText"],
            ["Requirement", "Decision", "Question", "Task", "Risk", "Assumption", "Constraint", "ProgressClaim", "ResearchFinding"],
            ["implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy"],
            case.get("entityContext", []),
        )
        try:
            normalized = None
            for attempt in range(2):
                try:
                    result = await gateway.extract(
                        GatewayRequest(
                            schemaVersion="m3.v1",
                            modelId=settings.llm_model,
                            systemPrompt=system,
                            userPrompt=user,
                            responseSchema=_response_schema(),
                            timeoutSeconds=60,
                        )
                    )
                    normalized = normalize_extraction(case["rawText"], result.extraction, case.get("entityContext", []))
                    break
                except NormalizedGatewayError as error:
                    if attempt == 1 or error.error_class != "invalid_evidence":
                        raise
            assert normalized is not None
            outputs[case["id"]] = normalized.model_dump(mode="json", by_alias=True)
            completed += 1
        except Exception as error:  # noqa: BLE001 - report only normalized class safely
            cause = getattr(error, "__cause__", None)
            failures[case["id"]] = {
                "errorClass": getattr(error, "error_class", "provider_failure"),
                "httpStatus": getattr(cause, "status_code", None),
                "exceptionType": type(error).__name__,
                "causeType": type(cause).__name__ if cause is not None else None,
            }
    quality = evaluate(cases, outputs)
    report = {"status": "completed" if not failures and quality["status"] == "passed" else "failed", "datasetVersion": dataset["datasetVersion"], "caseCount": len(cases), "completed": completed, "errorClasses": failures, "quality": quality}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
