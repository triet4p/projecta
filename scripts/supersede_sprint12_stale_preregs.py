#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Close stale S12-f-02..04 preregistrations without mutating history."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "evaluation/sprint-12/optimization/experiment-registry.v10.json"
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-02-04-v3-supersession.v1.json"
TARGETS = ("s12-f-02", "s12-f-03", "s12-f-04")


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build_packet() -> dict[str, Any]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_id = {entry["experimentId"]: entry for entry in registry["experiments"]}
    entries = []
    for experiment_id in TARGETS:
        entry = by_id[experiment_id]
        entries.append(
            {
                "experimentId": experiment_id,
                "dimension": entry["dimension"],
                "historicalEntryDigest": _digest(entry),
                "historicalStatus": entry["status"],
                "historicalDatasetVersion": registry["datasetVersion"],
                "historicalManifestDigest": entry["datasetManifestDigest"],
                "replacementExperiment": "s12-f-09",
                "replacementDatasetVersion": "s12.corpus.atomic.v3.frozen",
                "replacementStatus": "CLOSED_SUPERSEDED_BEFORE_V3",
            }
        )
    return {
        "schemaVersion": "s12.f02-04-v3-supersession.v1",
        "status": "STALE_PREREGISTRATIONS_CLOSED_BEFORE_V3",
        "sourceRegistry": {
            "path": str(REGISTRY.relative_to(ROOT)).replace("\\", "/"),
            "fileDigest": _file_digest(REGISTRY),
            "registryDatasetVersion": registry["datasetVersion"],
            "registryManifestDigest": registry["datasetManifestDigest"],
        },
        "experiments": entries,
        "historicalRegistryImmutable": True,
        "replacement": {
            "experimentId": "s12-f-09",
            "datasetVersion": "s12.corpus.atomic.v3.frozen",
            "manifestPath": "evaluation/sprint-12/corpus/v3-frozen/atomic-manifest.v1.json",
            "providerExecutionAuthorized": False,
            "heldOutInspected": False,
        },
        "rawSensitiveDataIncluded": False,
    }


def main() -> None:
    packet = build_packet()
    DEFAULT_OUTPUT.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": packet["status"], "closedExperiments": [entry["experimentId"] for entry in packet["experiments"]]}, indent=2))


if __name__ == "__main__":
    main()
