#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Record a non-mutating review of the supersession development slice."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v1.json"
MANIFEST_PATH = (
    ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v1.json"
)
OUTPUT_PATH = ROOT / "evaluation/sprint-12/baseline/supersession-review.v1.json"


def _digest(value: object) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def main() -> None:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    slices = {
        str(item["caseId"]): item.get("slice")
        for item in manifest["atomicCases"]
        if isinstance(item, dict)
    }
    entries: list[dict[str, object]] = []
    for case in corpus["cases"]:
        case_id = str(case["caseId"])
        if slices.get(case_id) != "contradiction-or-supersession":
            continue
        gold = case["gold"]
        source = case["source"]["rawText"]
        first_sentence_end = source.find(".") + 1
        entities = [item for item in gold["entities"] if isinstance(item, dict)]
        sentence_span_matches = [
            item.get("span", {}).get("start") == 0
            and item.get("span", {}).get("end") == first_sentence_end
            for item in entities
            if isinstance(item.get("span"), dict)
        ]
        semantic_gaps = [
            item for item in gold.get("semanticGaps", []) if isinstance(item, dict)
        ]
        entries.append(
            {
                "caseId": case_id,
                "goldDigest": _digest(gold),
                "goldEntitySpans": [
                    {
                        "start": item.get("span", {}).get("start"),
                        "end": item.get("span", {}).get("end"),
                    }
                    for item in entities
                    if isinstance(item.get("span"), dict)
                ],
                "goldRelationPredicates": [
                    item.get("predicate")
                    for item in gold.get("relations", [])
                    if isinstance(item, dict)
                ],
                "containsSupersedesSemanticGap": any(
                    item.get("candidateReleasedTerm") == "supersedes"
                    for item in semantic_gaps
                ),
                "entitySpanMatchesFirstSentence": any(sentence_span_matches),
            }
        )
    artifact = {
        "schemaVersion": "s12.supersession-review.v1",
        "status": "REVIEW_REQUIRED_BEFORE_STABILITY_PROMOTION",
        "datasetVersion": corpus.get("datasetVersion"),
        "corpusDigest": "sha256:" + hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest(),
        "guideVersions": ["annotation-guide.v1", "annotation-guide.v1.1"],
        "slice": "contradiction-or-supersession",
        "caseCount": len(entries),
        "cases": entries,
        "policyReview": {
            "minimalEvidencePolicy": "annotation-guide.v1 requires the smallest phrase expressing the complete semantic item.",
            "relationEvidencePolicy": "annotation-guide.v1 permits full clause/sentence evidence for relations.",
            "potentialEntitySpanTension": any(
                item["entitySpanMatchesFirstSentence"] for item in entries
            ),
            "goldChanged": False,
            "silentGoldRewrite": False,
            "newDatasetVersionRequiredIfAdjudicationChangesGold": True,
        },
        "contractBoundary": {
            "supersedesIsReleasedOntologyTerm": True,
            "supersedesIsCurrentAtomicCandidatePredicate": False,
            "ontologyChangeRequired": False,
            "candidateContractGap": True,
        },
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    OUTPUT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": artifact["status"],
                "caseCount": artifact["caseCount"],
                "potentialEntitySpanTension": artifact["policyReview"][
                    "potentialEntitySpanTension"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
