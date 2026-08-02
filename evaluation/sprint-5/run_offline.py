"""Deterministic Sprint 5 replay evaluation runner."""

import json
import sys
from pathlib import Path

from metrics_runner import evaluate

ROOT = Path(__file__).parent


def main() -> int:
    dataset = json.loads((ROOT / "dataset.v1.json").read_text(encoding="utf-8"))
    replay = json.loads((ROOT / "replay_outputs.v1.json").read_text(encoding="utf-8"))["responses"]
    missing = [case["id"] for case in dataset["cases"] if case["id"] not in replay]
    if missing:
        print(json.dumps({"status": "failed", "error": "missing_replay_cases", "cases": missing}, indent=2))
        return 1
    report = evaluate(dataset["cases"], replay)
    report.update({"datasetVersion": dataset["datasetVersion"], "schemaVersion": dataset["schemaVersion"], "caseCount": len(dataset["cases"])})
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    raise SystemExit(main())
