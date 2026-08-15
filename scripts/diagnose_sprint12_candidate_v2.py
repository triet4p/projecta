"""Diagnose only the failed m3.v2 development candidate cases."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import cast

import httpx
from openai import AsyncOpenAI
from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.prompt import build_extraction_prompt
from projecta_api.extraction.service import _response_schema
from projecta_api.llm.gateway import NormalizedGatewayError
from projecta_api.llm.openai_responses import _materialize_entity_evidence
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = (
    ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-development.v1.json"
)
OUTPUT_PATH = (
    ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-diagnostics.v1.json"
)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validation_classes(error: ValidationError) -> list[str]:
    classes: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item.get("loc", ()))
        message = str(item.get("msg", ""))
        if "candidateId" in location or "candidateId" in message:
            classes.append("candidate_id_shape_or_uniqueness")
        elif "predicate" in location or "predicate" in message:
            classes.append("allowlist_vocabulary")
        elif "abstention" in message:
            classes.append("abstention_conflict")
        else:
            classes.append("json_or_schema_shape")
    return sorted(set(classes))


async def main_async() -> dict[str, object]:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    case_ids = [str(item["caseId"]) for item in candidate["failures"]]
    corpus = json.loads(
        (
            ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v1.json"
        ).read_text(encoding="utf-8")
    )
    cases = {str(case["caseId"]): case for case in corpus["cases"]}
    environment = os.environ
    client = AsyncOpenAI(
        api_key=environment["PROJECTA_LLM_API_KEY"],
        base_url=environment["PROJECTA_LLM_BASE_URL"],
        max_retries=0,
        timeout=httpx.Timeout(60.0, connect=10.0, read=60.0, write=30.0, pool=10.0),
    )
    entity_types = [
        "Requirement",
        "Decision",
        "Question",
        "Task",
        "Risk",
        "Assumption",
        "Constraint",
        "ProgressClaim",
        "ResearchFinding",
    ]
    predicates = [
        "implements",
        "blocks",
        "dependsOn",
        "supports",
        "answers",
        "resolves",
        "constrainedBy",
    ]
    entries: list[dict[str, object]] = []
    try:
        for case_id in case_ids:
            case = cases[case_id]
            source = str(cast(dict[str, object], case["source"])["rawText"])
            system, user = build_extraction_prompt(
                source, entity_types, predicates, [], schema_version="m3.v2"
            )
            user += (
                "\nContract m3.v2: assign every emitted entity a unique local candidateId. "
                "Relation endpoints may reference local candidate IDs. Return exact evidence "
                "text and one-based occurrence; do not return offsets."
            )
            system += "\nExact JSON Schema to satisfy:\n" + json.dumps(
                _response_schema(schema_version="m3.v2"),
                ensure_ascii=False,
                sort_keys=True,
            )
            response = await client.chat.completions.create(
                model=environment["PROJECTA_LLM_MODEL"],
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_tokens=4096,
                extra_body={"thinking": {"type": "disabled"}},
                timeout=60,
            )
            content = getattr(response.choices[0].message, "content", None)
            if not isinstance(content, str):
                payload: object = None
                classes = ["missing_provider_json"]
            else:
                try:
                    payload = json.loads(content)
                    hydrated = _materialize_entity_evidence(payload, source)
                    hydrated = {
                        **cast(dict[str, object], hydrated),
                        "schemaVersion": "m3.v2",
                        "modelId": "diagnostic",
                        "modelVersion": "diagnostic",
                    }
                    ExtractionResponse.model_validate(hydrated)
                    classes = ["no_reproducible_contract_failure"]
                except json.JSONDecodeError:
                    payload = content
                    classes = ["malformed_json"]
                except NormalizedGatewayError as error:
                    classes = [f"normalizer_{error.error_class}"]
                except ValidationError as error:
                    classes = _validation_classes(error)
            entries.append(
                {
                    "caseId": case_id,
                    "sourceText": source,
                    "sourceDigest": _digest(source),
                    "diagnosticClasses": classes,
                    "providerPayload": payload,
                }
            )
    finally:
        await client.close()
    return {
        "schemaVersion": "s12.contract-candidate-v2-diagnostics.v1",
        "status": "CONTRACT_CANDIDATE_DIAGNOSTICS_COMPLETE",
        "contractVersion": "m3.v2",
        "candidateReportDigest": "sha256:"
        + hashlib.sha256(CANDIDATE_PATH.read_bytes()).hexdigest(),
        "caseCount": len(entries),
        "syntheticOnly": True,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "credentialsPersisted": False,
        "entries": entries,
    }


def main() -> None:
    result = asyncio.run(main_async())
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": result["status"], "caseCount": result["caseCount"]},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
