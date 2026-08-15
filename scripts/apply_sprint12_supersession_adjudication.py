#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Publish Sprint 12 corpus v2 with the adjudicated supersession decision."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/sprint-12/corpus"
BASELINE = ROOT / "evaluation/sprint-12/baseline"

ATOMIC_V1 = CORPUS / "atomic-development-validation.v1.json"
ATOMIC_V2 = CORPUS / "atomic-development-validation.v2.json"
SCENARIO_V1 = CORPUS / "scenario-development-validation.v1.json"
SCENARIO_V2 = CORPUS / "scenario-development-validation.v2.json"
MANIFEST_V1 = CORPUS / "manifests/development-validation.manifest.v1.json"
MANIFEST_V2 = CORPUS / "manifests/development-validation.manifest.v2.json"
ROOT_MANIFEST_V1 = CORPUS / "manifest.v1.json"
ROOT_MANIFEST_V2 = CORPUS / "manifest.v2.json"
ADJUDICATION = BASELINE / "supersession-adjudication.v2.json"
REVIEW_V1 = BASELINE / "supersession-review.v1.json"
REVIEW_V2 = BASELINE / "supersession-review.v2.json"


def digest(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    atomic_v1 = json.loads(ATOMIC_V1.read_text(encoding="utf-8"))
    manifest_v1 = json.loads(MANIFEST_V1.read_text(encoding="utf-8"))
    scenario_v1 = json.loads(SCENARIO_V1.read_text(encoding="utf-8"))
    root_manifest_v1 = json.loads(ROOT_MANIFEST_V1.read_text(encoding="utf-8"))
    slice_by_case = {
        str(item["caseId"]): item.get("slice")
        for item in manifest_v1["atomicCases"]
        if isinstance(item, dict)
    }
    atomic_v2 = copy.deepcopy(atomic_v1)
    changed_case_ids: list[str] = []
    abstention_reason = (
        "supersession clause is not an independently supported Requirement; "
        "the supersedes predicate is outside the current candidate allowlist"
    )
    for case in atomic_v2["cases"]:
        case_id = str(case["caseId"])
        if slice_by_case.get(case_id) != "contradiction-or-supersession":
            continue
        semantic_gaps = copy.deepcopy(case["gold"].get("semanticGaps", []))
        case["gold"] = {
            "entities": [],
            "relations": [],
            "links": [],
            "abstention": {"required": True, "reason": abstention_reason},
            "semanticGaps": semantic_gaps,
        }
        changed_case_ids.append(case_id)
    atomic_v2["datasetVersion"] = "s12.corpus.atomic.v2"
    atomic_v2["status"] = "OWNER_DELEGATED_AI_REVIEW_FIXTURE_WITH_ADJUDICATION_AMENDMENT"
    write_json(ATOMIC_V2, atomic_v2)

    manifest_v2 = copy.deepcopy(manifest_v1)
    manifest_v2["manifestVersion"] = "s12.corpus.manifest.v2"
    manifest_v2["status"] = "FROZEN_SYNTHETIC_PREPARATION_FIXTURE_WITH_ADJUDICATION_AMENDMENT"
    case_by_id = {str(case["caseId"]): case for case in atomic_v2["cases"]}
    for item in manifest_v2["atomicCases"]:
        case = case_by_id.get(str(item["caseId"]))
        if case is not None:
            item["caseDigest"] = digest(case)
    manifest_v2["manifestDigest"] = digest(
        {"atomicCases": manifest_v2["atomicCases"], "scenarios": manifest_v2["scenarios"]}
    )
    write_json(MANIFEST_V2, manifest_v2)

    scenario_v2 = copy.deepcopy(scenario_v1)
    scenario_v2["datasetVersion"] = "s12.corpus.scenario.v2"
    scenario_v2["status"] = "OWNER_DELEGATED_AI_REVIEW_FIXTURE_BOUND_TO_ATOMIC_V2"
    write_json(SCENARIO_V2, scenario_v2)

    root_manifest_v2 = copy.deepcopy(root_manifest_v1)
    root_manifest_v2["datasetVersion"] = "s12.corpus.v2"
    root_manifest_v2["atomicManifest"] = "manifests/development-validation.manifest.v2.json"
    root_manifest_v2["supersessionAdjudication"] = "../baseline/supersession-adjudication.v2.json"
    write_json(ROOT_MANIFEST_V2, root_manifest_v2)

    for source_name, target_name, dataset_version in (
        ("gold/atomic-gold.v1.json", "gold/atomic-gold.v2.json", "s12.corpus.atomic-gold.v2"),
        ("gold/scenario-gold.v1.json", "gold/scenario-gold.v2.json", "s12.corpus.scenario-gold.v2"),
        ("gold/retrieval-gold.v1.json", "gold/retrieval-gold.v2.json", "s12.corpus.retrieval-gold.v2"),
        ("gold/business-review-gold.v1.json", "gold/business-review-gold.v2.json", "s12.corpus.review-gold.v2"),
        ("qa/qa-report.v1.json", "qa/qa-report.v2.json", "s12.corpus.qa.v2"),
        ("qa/adjudication-log.v1.json", "qa/adjudication-log.v2.json", "s12.corpus.adjudication.v2"),
        (
            "qa/owner-delegated-ai-review.v1.json",
            "qa/owner-delegated-ai-review.v2.json",
            "s12.corpus.owner-delegated-ai-review.v2",
        ),
    ):
        source = CORPUS / source_name
        target = CORPUS / target_name
        value = json.loads(source.read_text(encoding="utf-8"))
        version_key = next(
            (key for key in ("datasetVersion", "reportVersion", "logVersion", "reviewVersion") if key in value),
            None,
        )
        if version_key:
            value[version_key] = dataset_version
        value["adjudicationAmendment"] = "supersession-adjudication.v2.json"
        if target_name == "gold/atomic-gold.v2.json":
            value["cases"] = [
                {"caseId": case["caseId"], "gold": case["gold"]}
                for case in atomic_v2["cases"]
            ]
        write_json(target, value)

    adjudication = {
        "schemaVersion": "s12.supersession-adjudication.v2",
        "status": "ADJUDICATED_DATASET_AMENDMENT_PUBLISHED",
        "decision": {
            "entities": [],
            "relations": [],
            "links": [],
            "abstentionRequired": True,
            "semanticGapPreserved": "candidate-contract-supersedes",
        },
        "rationale": "A supersession clause alone does not establish a standalone Requirement under the minimal-span and released-type rules; supersedes remains a candidate-contract gap.",
        "changedCaseCount": len(changed_case_ids),
        "changedCaseIds": changed_case_ids,
        "sourceDataset": {
            "path": "../corpus/atomic-development-validation.v1.json",
            "datasetVersion": atomic_v1["datasetVersion"],
            "fileDigest": file_digest(ATOMIC_V1),
            "contentDigest": digest(atomic_v1),
        },
        "publishedDataset": {
            "path": "../corpus/atomic-development-validation.v2.json",
            "datasetVersion": atomic_v2["datasetVersion"],
            "fileDigest": file_digest(ATOMIC_V2),
            "contentDigest": digest(atomic_v2),
        },
        "sourceManifestDigest": manifest_v1["manifestDigest"],
        "publishedManifestDigest": manifest_v2["manifestDigest"],
        "goldChanged": True,
        "goldChangedSilently": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    write_json(ADJUDICATION, adjudication)
    review_v2 = json.loads(REVIEW_V1.read_text(encoding="utf-8"))
    review_v2["schemaVersion"] = "s12.supersession-review.v2"
    review_v2["status"] = "ADJUDICATED_DATASET_AMENDMENT_PUBLISHED"
    review_v2["publishedDatasetVersion"] = atomic_v2["datasetVersion"]
    review_v2["adjudicationArtifact"] = "supersession-adjudication.v2.json"
    review_v2["policyReview"] = {
        **review_v2["policyReview"],
        "potentialEntitySpanTension": False,
        "adjudicated": True,
        "goldChanged": True,
        "silentGoldRewrite": False,
        "decision": "abstain-with-semantic-gap",
    }
    write_json(REVIEW_V2, review_v2)
    print(
        json.dumps(
            {
                "status": adjudication["status"],
                "changedCaseCount": adjudication["changedCaseCount"],
                "datasetVersion": atomic_v2["datasetVersion"],
                "manifestDigest": manifest_v2["manifestDigest"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
