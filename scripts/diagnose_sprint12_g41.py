"""Run bounded G4.1 failure exemplars without mutating the historical baseline."""

import asyncio
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

import httpx
from openai import AsyncOpenAI
from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.normalize import normalize_extraction
from projecta_api.extraction.prompt import build_extraction_prompt
from projecta_api.extraction.service import _response_schema
from projecta_api.llm.gateway import NormalizedGatewayError
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evaluation/sprint-12/baseline/baseline-report.v1.json"
OUTPUT_PATH = ROOT / "evaluation/sprint-12/baseline/g4.1-failure-exemplars.v1.json"
MAX_INVALID_EVIDENCE_SAMPLE = 16


def _load_evaluator() -> Any:
    path = ROOT / "scripts/sprint12_evaluator.py"
    spec = importlib.util.spec_from_file_location("sprint12_evaluator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Sprint 12 evaluator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slice_map(manifest: dict[str, object]) -> dict[str, str]:
    return {
        str(item["caseId"]): str(item.get("slice", "unknown"))
        for item in cast(list[dict[str, object]], manifest["atomicCases"])
    }


def select_case_ids(
    report: dict[str, object], manifest: dict[str, object]
) -> list[str]:
    """Select all schema failures and a deterministic 16-case stratified sample."""
    taxonomy = cast(dict[str, object], report["errorTaxonomy"])
    observations = cast(list[dict[str, object]], taxonomy["observations"])
    schema_ids = sorted(
        str(item["caseId"])
        for item in observations
        if item.get("failureClass") == "schema_invalid"
    )
    invalid_ids = [
        str(item["caseId"])
        for item in observations
        if item.get("failureClass") == "invalid_evidence"
    ]
    slices = _slice_map(manifest)
    preferred = {
        "temporal-change",
        "unicode-and-noisy-text",
        "contradiction-or-supersession",
        "duplicate-evidence",
    }
    chosen: list[str] = []
    for slice_name in sorted(preferred):
        candidates = sorted(
            case_id for case_id in invalid_ids if slices.get(case_id) == slice_name
        )
        if candidates:
            chosen.append(candidates[0])
    for case_id in sorted(
        invalid_ids, key=lambda value: (slices.get(value, "unknown"), value)
    ):
        if case_id not in chosen and len(chosen) < MAX_INVALID_EVIDENCE_SAMPLE:
            chosen.append(case_id)
    return schema_ids + chosen[:MAX_INVALID_EVIDENCE_SAMPLE]


def classify_payload(payload: object, source: str, evaluator: Any) -> list[str]:
    """Classify observable contract failures without guessing model intent."""
    if not isinstance(payload, dict):
        return ["json_or_schema_shape"]
    raw = cast(dict[str, object], payload)
    if raw.get("abstentionReason") and any(
        raw.get(name) for name in ("entities", "relations", "links")
    ):
        return ["abstention_conflict"]
    hydrated = {
        **raw,
        "schemaVersion": "m3.v1",
        "modelId": "diagnostic",
        "modelVersion": "diagnostic",
    }
    try:
        response = ExtractionResponse.model_validate(hydrated)
    except ValidationError:
        return ["json_or_schema_shape"]
    failures: list[str] = []
    for category, candidates in (
        ("entity", response.entities),
        ("relation", response.relations),
        ("link", response.links),
    ):
        for candidate in candidates:
            span = candidate.evidence
            if span.end_offset > len(source):
                failures.append(f"{category}_offset_out_of_range")
            elif source[span.start_offset : span.end_offset] != span.text:
                failures.append(f"{category}_evidence_text_mismatch")
    if response.relations:
        failures.append("relation_endpoint_unrepresentable_without_bounded_context")
    try:
        normalize_extraction(source, response, [])
    except NormalizedGatewayError as error:
        failures.append(f"normalizer_{error.error_class}")
    return sorted(set(failures)) or ["no_reproducible_contract_failure"]


async def _run() -> dict[str, object]:
    evaluator = _load_evaluator()
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    loaded = evaluator.load_dataset(
        ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v1.json",
        ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v1.json",
        ROOT
        / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v1.json",
    )
    selected = set(select_case_ids(report, loaded.manifest))
    cases = [case for case in loaded.cases if str(case["caseId"]) in selected]
    environment = os.environ
    required = evaluator.missing_runtime_configuration(environment)
    if required:
        raise RuntimeError("diagnostic runtime configuration is missing")
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
    slices = _slice_map(loaded.manifest)
    observations = cast(
        list[dict[str, object]],
        cast(dict[str, object], report["errorTaxonomy"])["observations"],
    )
    reported = {str(item["caseId"]): str(item["failureClass"]) for item in observations}
    entries: list[dict[str, object]] = []
    try:
        for case in cases:
            case_id = str(case["caseId"])
            source = str(cast(dict[str, object], case["source"])["rawText"])
            system, user = build_extraction_prompt(
                source, entity_types, predicates, [], schema_version="m3.v1"
            )
            system += "\nExact JSON Schema to satisfy:\n" + json.dumps(
                _response_schema(), ensure_ascii=False, sort_keys=True
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
                parse_status = "missing_provider_json"
            else:
                try:
                    payload = json.loads(content)
                    parse_status = "json"
                except json.JSONDecodeError:
                    payload = content
                    parse_status = "malformed_json"
            entries.append(
                {
                    "caseId": case_id,
                    "split": case["split"],
                    "slice": slices.get(case_id, "unknown"),
                    "sourceText": source,
                    "sourceDigest": _digest(source),
                    "reportedFailureClass": reported[case_id],
                    "parseStatus": parse_status,
                    "diagnosticClasses": classify_payload(payload, source, evaluator),
                    "providerPayload": payload,
                }
            )
    finally:
        await client.close()
    return {
        "schemaVersion": "s12.g4.1.failure-exemplars.v1",
        "status": "G4_1_DIAGNOSTICS_COMPLETE",
        "syntheticOnly": True,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "credentialsPersisted": False,
        "baselineReportDigest": "sha256:"
        + hashlib.sha256(REPORT_PATH.read_bytes()).hexdigest(),
        "samplePolicy": {
            "schemaInvalidCount": 7,
            "invalidEvidenceSampleCount": MAX_INVALID_EVIDENCE_SAMPLE,
            "totalCaseCount": len(entries),
            "strata": [
                "temporal-change",
                "unicode-and-noisy-text",
                "contradiction-or-supersession",
                "duplicate-evidence",
            ],
        },
        "entries": entries,
    }


def main() -> None:
    result = asyncio.run(_run())
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": result["status"], "caseCount": len(result["entries"])},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
