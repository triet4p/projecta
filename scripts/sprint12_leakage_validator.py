#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Validate Sprint 12 split leakage without reading held-out payloads.

The v2 corpus remains an immutable historical fixture. This validator is a new
diagnostic contract: it canonicalizes source text for semantic-template
comparison, groups scenario lineages, and reports only hashes and identifiers.
It never loads a test payload; test custody is reported as unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/sprint-12/corpus"
VALIDATOR_VERSION = "s12.leakage-validator.v2"
GENERATOR_MARKER_PATTERN = re.compile(
    r"\b(?:evidence\s+marker|distinguishing\s+phrase)\b"
    r"[^.!?;\n]*(?:[.!?;]|$)",
    re.IGNORECASE,
)
IDENTIFIER_PATTERN = re.compile(
    r"(?<![\w])(?:[a-z]+\d+[a-z0-9_-]*|[a-z0-9]+[-_]"
    r"[a-z0-9_-]*\d[a-z0-9_-]*)(?![\w])",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?(?![\w])")
WHITESPACE_PATTERN = re.compile(r"\s+")


class LeakageValidationError(ValueError):
    """Raised when the validator receives an unsafe or malformed input."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonicalize_source(text: str) -> str:
    """Return a semantic-template key without IDs, numbers, or punctuation."""

    value = unicodedata.normalize("NFKC", text).casefold()
    value = GENERATOR_MARKER_PATTERN.sub(" ", value)
    value = IDENTIFIER_PATTERN.sub(" <id> ", value)
    value = NUMBER_PATTERN.sub(" <num> ", value)
    value = "".join(
        character if not unicodedata.category(character).startswith("P") else " "
        for character in value
    )
    return WHITESPACE_PATTERN.sub(" ", value).strip()


def contains_generator_marker(text: str) -> bool:
    return bool(GENERATOR_MARKER_PATTERN.search(text))


def _cluster_rows(groups: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    rows = []
    for key, records in groups.items():
        splits = sorted({record["split"] for record in records})
        if len(records) < 2:
            continue
        rows.append(
            {
                "templateHash": sha256_text(key),
                "caseCount": len(records),
                "splits": splits,
                "caseIds": sorted(record["caseId"] for record in records),
            }
        )
    return sorted(rows, key=lambda row: (-row["caseCount"], row["templateHash"]))


def _cross_split(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if len(row["splits"]) > 1]


def analyze_atomic_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze atomic payload records while retaining no source text in output."""

    if any(case.get("split") == "test" for case in cases):
        raise LeakageValidationError(
            "test payload was supplied; leakage validation must not read held-out data"
        )
    template_groups: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    content_groups: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    marker_case_ids: list[str] = []
    for case in cases:
        case_id = str(case["caseId"])
        split = str(case["split"])
        source = case.get("source")
        if not isinstance(source, dict) or not isinstance(source.get("rawText"), str):
            raise LeakageValidationError(f"missing rawText for atomic case {case_id}")
        raw_text = source["rawText"]
        record = {"caseId": case_id, "split": split}
        template_groups[canonicalize_source(raw_text)].append(record)
        content_digest = str(source.get("contentDigest", sha256_text(raw_text)))
        content_groups[content_digest].append(record)
        if contains_generator_marker(raw_text):
            marker_case_ids.append(case_id)

    template_clusters = _cluster_rows(template_groups)
    content_clusters = _cluster_rows(content_groups)
    return {
        "payloadCaseCount": len(cases),
        "splitCounts": {
            split: sum(case.get("split") == split for case in cases)
            for split in ("development", "validation")
        },
        "generatorMarkerCaseCount": len(marker_case_ids),
        "generatorMarkerCaseIds": sorted(marker_case_ids),
        "normalizedTemplateClusterCount": len(template_clusters),
        "normalizedTemplateClusters": template_clusters,
        "crossSplitNormalizedTemplateClusters": _cross_split(template_clusters),
        "exactContentDuplicateClusters": content_clusters,
        "crossSplitExactContentDuplicateClusters": _cross_split(content_clusters),
        "pass": not _cross_split(template_clusters)
        and not _cross_split(content_clusters),
    }


def _scenario_semantic_hash(scenario: dict[str, Any]) -> str:
    projection = {
        "events": scenario.get("events", []),
        "checkpoints": scenario.get("checkpoints", []),
        "competencyAnswers": scenario.get("competencyAnswers", []),
    }
    canonical = json.dumps(
        projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256_text(canonical)


def analyze_scenarios(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect reused source lineages and conflicting scenario gold."""

    lineage_groups: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for scenario in scenarios:
        scenario_id = str(scenario["scenarioId"])
        source_manifest = scenario.get("sourceManifest")
        if not isinstance(source_manifest, list) or not all(
            isinstance(case_id, str) for case_id in source_manifest
        ):
            raise LeakageValidationError(f"invalid sourceManifest for {scenario_id}")
        lineage_key = "|".join(source_manifest)
        lineage_groups[lineage_key].append(
            {
                "scenarioId": scenario_id,
                "split": str(scenario["split"]),
                "semanticHash": _scenario_semantic_hash(scenario),
            }
        )

    reused_lineages = []
    cross_split_lineages = []
    conflicting_gold = []
    for lineage_key, records in lineage_groups.items():
        if len(records) < 2:
            continue
        row = {
            "lineageHash": sha256_text(lineage_key),
            "scenarioCount": len(records),
            "scenarioIds": sorted(record["scenarioId"] for record in records),
            "splits": sorted({record["split"] for record in records}),
            "semanticHashes": sorted({record["semanticHash"] for record in records}),
        }
        reused_lineages.append(row)
        if len(row["splits"]) > 1:
            cross_split_lineages.append(row)
        if len(row["semanticHashes"]) > 1:
            conflicting_gold.append(row)

    return {
        "payloadScenarioCount": len(scenarios),
        "uniqueSourceLineageCount": len(lineage_groups),
        "reusedSourceLineageGroups": sorted(
            reused_lineages, key=lambda row: row["lineageHash"]
        ),
        "crossSplitSourceLineageGroups": sorted(
            cross_split_lineages, key=lambda row: row["lineageHash"]
        ),
        "conflictingGoldGroups": sorted(
            conflicting_gold, key=lambda row: row["lineageHash"]
        ),
        "pass": not reused_lineages and not cross_split_lineages and not conflicting_gold,
    }


def validate(
    atomic_payload: dict[str, Any],
    scenario_payload: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Produce a fail-closed leakage report for repository-visible payloads."""

    atomic = analyze_atomic_cases(atomic_payload["cases"])
    scenarios = analyze_scenarios(scenario_payload["scenarios"])
    test_counts = {
        "atomic": manifest.get("atomicCounts", {}).get("test"),
        "scenarios": manifest.get("scenarioCounts", {}).get("test"),
    }
    known_leakage = not atomic["pass"] or not scenarios["pass"]
    return {
        "reportVersion": VALIDATOR_VERSION,
        "datasetVersion": atomic_payload.get("datasetVersion"),
        "status": "BLOCKED_KNOWN_LEAKAGE" if known_leakage else "CLEAN_VISIBLE_SPLITS",
        "readScope": {
            "atomicPayloadSplits": atomic["splitCounts"],
            "scenarioPayloadSplits": {
                split: sum(
                    scenario.get("split") == split
                    for scenario in scenario_payload["scenarios"]
                )
                for split in ("development", "validation")
            },
            "testPayloadRead": False,
            "testPayloadStatus": "not-available-custody",
            "testManifestCounts": test_counts,
        },
        "atomic": atomic,
        "scenarios": scenarios,
        "gates": {
            "visibleDevelopmentValidationLeakage": not known_leakage,
            "fullSplitLeakage": False,
            "fullSplitLeakageReason": "test payload is sealed and was not read",
        },
    }


def validate_paths(
    atomic_path: Path, scenario_path: Path, manifest_path: Path
) -> dict[str, Any]:
    return validate(read_json(atomic_path), read_json(scenario_path), read_json(manifest_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--atomic",
        type=Path,
        default=CORPUS / "atomic-development-validation.v2.json",
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        default=CORPUS / "scenario-development-validation.v2.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=CORPUS / "manifest.v2.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_paths(args.atomic, args.scenario, args.manifest)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
