#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Bind the approved S12-77 candidate model before execution."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "evaluation/sprint-12/optimization/s12-77-model-preregistration.v1.json"
OUTPUT_PATH = ROOT / "evaluation/sprint-12/optimization/s12-77-model-preregistration.v2.json"


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        raise SystemExit("usage: bind_sprint12_s77.py <candidate-model>")
    if OUTPUT_PATH.exists():
        raise SystemExit(f"refusing to overwrite existing binding: {OUTPUT_PATH}")
    candidate_model = sys.argv[1].strip()
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    artifact = copy.deepcopy(source)
    artifact["artifactVersion"] = "s12.s77.model-preregistration.v2"
    artifact["status"] = "AUTHORIZED_NOT_EXECUTED"
    artifact["candidateModel"] = candidate_model
    artifact["candidateModelSelectionRequired"] = False
    artifact["executionAuthorized"] = True
    artifact["modelBinding"] = {
        "controlModel": artifact["controlModel"],
        "candidateModel": candidate_model,
        "changedDimension": "model",
        "configurationDigest": digest(
            {
                "controlModel": artifact["controlModel"],
                "candidateModel": candidate_model,
                "fixedArtifacts": artifact["fixedArtifacts"],
                "datasetManifestDigest": artifact["datasetManifestDigest"],
            }
        ),
    }
    artifact["semanticThresholds"] = {
        "entityMacroF1MinimumDelta": 0.05,
        "abstentionAccuracyMinimumDelta": 0.05,
        "hallucinationRateMaximumIncrease": 0.0,
        "relationMacroF1MinimumDelta": 0.0,
    }
    artifact["sourcePreregistration"] = {
        "artifact": SOURCE_PATH.name,
        "digest": "sha256:" + hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(),
    }
    OUTPUT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": artifact["status"], "candidateModel": candidate_model}, sort_keys=True))


if __name__ == "__main__":
    main()
