"""Contract tests for stale S12-f-02..04 preregistration closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "evaluation/sprint-12/optimization/s12-f-02-04-v3-supersession.v1.json"
REGISTRY = ROOT / "evaluation/sprint-12/optimization/experiment-registry.v10.json"


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_stale_preregs_are_closed_as_a_versioned_historical_amendment() -> None:
    packet = read_json(PACKET)
    registry = read_json(REGISTRY)
    assert packet["schemaVersion"] == "s12.f02-04-v3-supersession.v1"
    assert packet["status"] == "STALE_PREREGISTRATIONS_CLOSED_BEFORE_V3"
    assert packet["historicalRegistryImmutable"] is True
    assert [entry["experimentId"] for entry in packet["experiments"]] == ["s12-f-02", "s12-f-03", "s12-f-04"]
    historical = {entry["experimentId"]: entry for entry in registry["experiments"]}
    for entry in packet["experiments"]:
        assert entry["historicalEntryDigest"] == digest(historical[entry["experimentId"]])
        assert entry["historicalStatus"] == "REGISTERED"
        assert entry["historicalDatasetVersion"] == "s12.corpus.atomic.v2"
        assert entry["replacementStatus"] == "CLOSED_SUPERSEDED_BEFORE_V3"


def test_supersession_points_to_frozen_v3_without_authorizing_execution() -> None:
    replacement = read_json(PACKET)["replacement"]
    assert replacement["experimentId"] == "s12-f-09"
    assert replacement["datasetVersion"] == "s12.corpus.atomic.v3.frozen"
    assert replacement["providerExecutionAuthorized"] is False
    assert replacement["heldOutInspected"] is False
