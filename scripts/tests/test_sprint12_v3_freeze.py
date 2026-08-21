"""Contract tests for the R15 v3 frozen development/validation bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "evaluation/sprint-12/corpus/v3-frozen"


def read_json(name: str) -> dict:
    return json.loads((FROZEN / name).read_text(encoding="utf-8"))


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_bundle_is_dev_validation_only_and_digest_bound() -> None:
    freeze = read_json("freeze-manifest.v1.json")
    assert freeze["schemaVersion"] == "s12.v3.freeze-manifest.v1"
    assert freeze["status"] == "V3_FROZEN_G31_C_PENDING"
    assert freeze["humanEvidence"] is False
    assert freeze["providerExecutionAuthorized"] is False
    assert freeze["heldOutInspected"] is False
    assert freeze["testPayloadPresent"] is False
    assert len(freeze["files"]) == 8
    for entry in freeze["files"]:
        assert entry["fileDigest"] == file_digest(FROZEN / entry["path"])


def test_frozen_payloads_preserve_scale_coverage_without_test_payload() -> None:
    atomic = read_json("atomic-v3.frozen.v1.json")
    atomic_manifest = read_json("atomic-manifest.v1.json")
    scenarios = read_json("scenario-v3.frozen.v1.json")
    scenario_manifest = read_json("scenario-manifest.v1.json")
    coverage = read_json("coverage.v1.json")["coverage"]
    assert atomic["datasetVersion"] == "s12.corpus.atomic.v3.frozen"
    assert scenarios["datasetVersion"] == "s12.corpus.scenario.v3.frozen"
    assert atomic_manifest["atomicCounts"] == {"development": 160, "validation": 48, "test": 0, "total": 208}
    assert scenario_manifest["scenarioCounts"] == {"development": 20, "validation": 6, "test": 0, "total": 26}
    assert len(atomic["cases"]) == 208
    assert len(scenarios["scenarios"]) == 26
    assert coverage["relationPositiveCases"] == 52
    assert coverage["relationNegativeCases"] == 156
    assert coverage["abstentionRequiredCases"] == 26


def test_frozen_qa_evidence_passes_and_keeps_gates_closed() -> None:
    qa = read_json("qa-report.v1.json")
    leakage = read_json("leakage.v1.json")
    provenance = read_json("provenance.v1.json")
    assert qa["status"] == "FROZEN_QA_PASS"
    assert all(qa["gates"].values())
    assert qa["diagnostics"]["spanErrors"] == []
    assert qa["diagnostics"]["scenarioShapeErrors"] == []
    assert qa["providerExecutionAuthorized"] is False
    assert qa["heldOutInspected"] is False
    assert leakage["status"] == "CLEAN_VISIBLE_SPLITS"
    assert leakage["crossSplitNormalizedTemplateClusters"] == []
    assert leakage["crossSplitExactContentDuplicates"] == []
    assert provenance["rawSensitiveDataIncluded"] is False
    assert provenance["testPayloadPresent"] is False
