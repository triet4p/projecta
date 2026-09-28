"""Run the bounded deterministic internal F-RF candidate without a provider.

This is deliberately a small rule-based candidate, not a substitute for the
released provider candidate or RM-67 human evidence. It exercises SourceVersion,
ExtractionResponse, normalization, and the evaluator on the internal PoC scope.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POC_PATH = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc.v1.json"
ATOMIC_PATH = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
OUTPUT_PATH = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v2.json"
REVIEW_PATH = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v2.json"

SIGNALS = (
    (re.compile(r"\b(requirement|requirements|req\.?|yêu cầu)\b", re.IGNORECASE), "Requirement"),
    (re.compile(r"\b(task|todo|việc|作業)\b", re.IGNORECASE), "Task"),
    (re.compile(r"\b(risk|rủi ro|リスク)\b", re.IGNORECASE), "Risk"),
    (re.compile(r"\b(decision|quyết định|決定)\b", re.IGNORECASE), "Decision"),
    (re.compile(r"\b(question|câu hỏi|質問)\b", re.IGNORECASE), "Question"),
)
ADVERSARIAL = re.compile(r"prompt injection|ignore previous|fabricated link|cross-project", re.IGNORECASE)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _file_digest(path: Path) -> str:
    return _digest(path.read_bytes())


def _stable(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _deterministic_response(raw_text: str, case_id: str) -> dict[str, Any]:
    if ADVERSARIAL.search(raw_text):
        return {
            "schemaVersion": "m3.v2",
            "modelId": "internal-deterministic-v1",
            "modelVersion": "v1",
            "entities": [],
            "relations": [],
            "links": [],
            "abstentionReason": "internal_poc_adversarial_input_abstain",
        }
    entities: list[dict[str, Any]] = []
    occupied: set[tuple[int, int]] = set()
    for signal, entity_type in SIGNALS:
        match = signal.search(raw_text)
        if match is None or (match.start(), match.end()) in occupied:
            continue
        occupied.add((match.start(), match.end()))
        entities.append(
            {
                "candidateId": f"poc-{case_id}-{len(entities) + 1}",
                "type": entity_type,
                "label": match.group(0),
                "evidence": {
                    "startOffset": match.start(),
                    "endOffset": match.end(),
                    "text": match.group(0),
                },
                "confidence": "0.50",
            }
        )
    if not entities:
        return {
            "schemaVersion": "m3.v2",
            "modelId": "internal-deterministic-v1",
            "modelVersion": "v1",
            "entities": [],
            "relations": [],
            "links": [],
            "abstentionReason": "internal_poc_no_allowlisted_signal",
        }
    return {
        "schemaVersion": "m3.v2",
        "modelId": "internal-deterministic-v1",
        "modelVersion": "v1",
        "entities": entities,
        "relations": [],
        "links": [],
    }


def run() -> tuple[dict[str, Any], dict[str, Any]]:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    import sprint12_evaluator as evaluator
    from projecta_api.extraction.contracts import ExtractionResponse
    from projecta_api.extraction.normalize import normalize_extraction
    from projecta_api.extraction.source_version import create_source_version

    poc = json.loads(POC_PATH.read_text(encoding="utf-8"))
    atomic = json.loads(ATOMIC_PATH.read_text(encoding="utf-8"))
    by_id = {case["caseId"]: case for case in atomic["cases"]}
    case_ids = poc["datasetBinding"]["representativeCaseIds"]
    scenario_ids = poc["datasetBinding"]["scenarioIds"]
    case_results: list[dict[str, Any]] = []
    review_records: list[dict[str, Any]] = []
    for index, case_id in enumerate(case_ids, 1):
        case = by_id[case_id]
        raw_text = case["source"]["rawText"]
        source = create_source_version(
            project_id="projecta-internal-poc",
            source_artifact_id=case_id,
            content=raw_text,
        )
        response = ExtractionResponse.model_validate(_deterministic_response(raw_text, case_id))
        normalized = normalize_extraction(raw_text, response, [])
        prediction = normalized.model_dump(mode="json", by_alias=True)
        gold = case["gold"]
        scored = evaluator.score_extraction(gold, prediction, ["implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy"])
        output_status = "abstained" if prediction.get("abstentionReason") else "scored"
        correction_class = "not-applicable" if output_status == "abstained" else "unchanged"
        review_records.append(
            {
                "recordId": f"poc-review-v2-{index:03d}",
                "caseId": case_id,
                "scenarioId": scenario_ids[index - 1],
                "sourceDigest": source.safe_dict()["canonicalContentDigest"],
                "candidateDigest": _digest(_stable(prediction)),
                "candidateOutputStatus": output_status,
                "finalDisposition": "abstained" if output_status == "abstained" else "confirmed",
                "correctionClass": correction_class,
                "semanticEditCount": 0,
                "effortProxySeconds": 1 + len(raw_text) // 120,
                "manualBaselineSeconds": None,
                "timingStatus": "agent-proxy-effort-only",
                "reviewer": "primary-agent-proxy",
                "eligibleForAcceptance": False,
                "unsupportedFinalizedAssertions": 0,
                "integrityStatus": "source-version-bound",
            }
        )
        case_results.append(
            {
                "caseId": case_id,
                "scenarioId": scenario_ids[index - 1],
                "status": output_status,
                "entityCount": len(prediction.get("entities", [])),
                "abstentionReason": prediction.get("abstentionReason"),
                "sourceVersion": source.safe_dict(),
                "score": scored,
            }
        )
    candidate = {
        "artifactVersion": "s12.f-rf.internal-poc-candidate.v2",
        "status": "INTERNAL_DEV_POC_EXECUTED",
        "candidateVersion": "m3.v2",
        "candidateKind": "deterministic-rule-boundary",
        "scope": "internal-development-representative-cases-only",
        "caseCount": len(case_results),
        "caseResults": case_results,
        "providerCalls": 0,
        "heldOutInspection": False,
        "assertedGraphMutation": False,
        "inferencePublication": False,
        "rawSensitiveDataIncluded": False,
        "pocProtocolDigest": _file_digest(POC_PATH),
        "candidateCodeDigest": _file_digest(Path(__file__)),
        "statusReason": "deterministic local rule candidate; no provider runtime or human evidence",
    }
    review = {
        "artifactVersion": "s12.f-rf.internal-poc-review.v2",
        "status": "POC_DIAGNOSTIC_NO_HUMAN_ACCEPTANCE",
        "candidatePath": "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v2.json",
        "candidateDigest": "sha256:" + "0" * 64,
        "reviewerMode": "AGENT_PROXY_NOT_HUMAN",
        "humanEvidence": False,
        "providerCalls": 0,
        "heldOutInspection": False,
        "manualBaseline": {"status": "NOT_RUN_NO_HUMAN_REVIEWER", "pairedRecords": 0},
        "records": review_records,
        "metrics": {
            "eligibleReviewedItems": len(review_records),
            "acceptedWithoutSemanticCorrection": {"numerator": 0, "rate": 0.0, "threshold": 0.7},
            "acceptedUnchangedOrMinor": {"numerator": 0, "rate": 0.0, "threshold": 0.85},
            "medianEffortProxySeconds": sorted(record["effortProxySeconds"] for record in review_records)[len(review_records) // 2],
            "manualBaselineReduction": None,
            "meanSemanticEditsPerReviewedItem": 0.0,
            "unsupportedFinalizedAssertions": {"numerator": 0, "denominator": 0, "status": "NOT_APPLICABLE_BLOCKS_GATE"},
            "reviewerAgreement": {"status": "NOT_APPLICABLE_BLOCKS_GATE", "independentRecords": 0},
            "gateStatus": "FAIL_NO_HUMAN_BASELINE_OR_AGREEMENT",
        },
        "nonClaims": [
            "agent-proxy review is not human or independent evidence",
            "effort proxy is not review latency and no manual baseline was run",
            "no RM-68 acceptance, external validation, business-quality claim, provider, held-out, or production authority",
        ],
    }
    return candidate, review


if __name__ == "__main__":
    candidate, review = run()
    OUTPUT_PATH.write_text(json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review["candidateDigest"] = _file_digest(OUTPUT_PATH)
    REVIEW_PATH.write_text(json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidateStatus": candidate["status"], "reviewStatus": review["status"], "caseCount": candidate["caseCount"], "providerCalls": candidate["providerCalls"]}, sort_keys=True))
