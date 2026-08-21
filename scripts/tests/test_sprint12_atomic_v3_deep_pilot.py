"""Contract tests for the authored Sprint 12 atomic v3 deep pilot."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evaluation/sprint-12/corpus/v3/atomic-deep-pilot.v1.json"
MANIFEST = ROOT / "evaluation/sprint-12/corpus/v3/manifest.v1.json"

SPEC = importlib.util.spec_from_file_location(
    "sprint12_leakage_validator", ROOT / "scripts/sprint12_leakage_validator.py"
)
assert SPEC is not None and SPEC.loader is not None
LEAKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LEAKAGE
SPEC.loader.exec_module(LEAKAGE)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_deep_pilot_has_six_lineages_and_lineage_disjoint_splits() -> None:
    dataset = read_json(DATASET)
    manifest = read_json(MANIFEST)
    cases = dataset["cases"]
    assert dataset["datasetVersion"] == "s12.corpus.atomic.v3.deep-pilot"
    assert len(cases) == 48
    assert manifest["atomicCounts"] == {
        "development": 32,
        "validation": 16,
        "test": 0,
        "total": 48,
    }
    lineages: dict[str, set[str]] = {}
    for case in cases:
        lineages.setdefault(case["scenarioId"], set()).add(case["split"])
    assert len(lineages) == 6
    assert all(len(splits) == 1 for splits in lineages.values())
    assert set(manifest["atomicCounts"]) == {"development", "validation", "test", "total"}
    assert manifest["testPayloadPresent"] is False


def test_deep_pilot_has_natural_variation_and_relation_depth() -> None:
    dataset = read_json(DATASET)
    cases = dataset["cases"]
    serialized = json.dumps(dataset, ensure_ascii=False)
    assert "Evidence marker" not in serialized
    assert "distinguishing phrase" not in serialized
    assert "sequence filler" not in serialized
    assert len({case["source"]["rawText"] for case in cases}) == 48
    assert sum(bool(case["gold"]["relations"]) for case in cases) == 15
    assert sum(case["gold"]["abstention"]["required"] for case in cases) == 6
    assert {case["source"]["language"] for case in cases} == {
        "en",
        "vi",
        "ja",
        "mixed",
    }
    leakage = LEAKAGE.analyze_atomic_cases(cases)
    assert leakage["crossSplitNormalizedTemplateClusters"] == []
    assert leakage["crossSplitExactContentDuplicateClusters"] == []


def test_deep_pilot_spans_relations_and_metadata_are_integrity_bound() -> None:
    dataset = read_json(DATASET)
    manifest = read_json(MANIFEST)
    manifest_by_id = {entry["caseId"]: entry for entry in manifest["atomicCases"]}
    for case in dataset["cases"]:
        source = case["source"]
        text = source["rawText"]
        assert source["origin"] == "agent-authored-synthetic"
        assert source["sensitivity"] == "synthetic"
        assert source["permissionRef"] == "sprint12-r09-deep-pilot-v1"
        assert source["contentDigest"] == "sha256:" + hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()
        assert manifest_by_id[case["caseId"]]["caseDigest"] == digest(case)
        entity_ids = {entity["id"] for entity in case["gold"]["entities"]}
        for entity in case["gold"]["entities"]:
            span = entity["span"]
            assert text[span["start"] : span["end"]] == span["text"]
            assert re.fullmatch(r"entity-[0-9]{2}", entity["id"])
        for relation in case["gold"]["relations"]:
            assert relation["sourceEntityId"] in entity_ids
            assert relation["targetEntityId"] in entity_ids
            span = relation["span"]
            assert text[span["start"] : span["end"]] == span["text"]
