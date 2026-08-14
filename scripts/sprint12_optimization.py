#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Sprint 12 Phase F controlled-optimization registry and G5 guards."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias, cast

JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)
JsonObject: TypeAlias = dict[str, JSONValue]
EVALUATOR_VERSION = "s12.evaluator.v1"
REGISTRY_VERSION = "s12.experiment-registry.v1"
DIMENSIONS = ("prompt", "context", "agent-workflow", "tool", "model")
REQUIRED_PRESERVED_ARTIFACTS = (
    "dataset",
    "evaluator",
    "ontology",
    "policy",
    "review-contract",
)


class OptimizationError(ValueError):
    """Raised when an experiment violates the controlled-optimization contract."""


def _object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise OptimizationError(f"{label} must be an object")
    return cast(JsonObject, value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise OptimizationError(f"{label} must be a non-empty string")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest(value: object) -> str:
    """Return a canonical JSON sha256 digest."""

    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def validate_experiment(spec: Mapping[str, object]) -> None:
    """Validate one registered experiment and its single-change boundary."""

    required = (
        "experimentId",
        "hypothesis",
        "dimension",
        "permittedSplit",
        "baselineConfigurationDigest",
        "candidateConfigurationDigest",
        "metricTarget",
        "stoppingRule",
        "changedArtifacts",
        "preservedArtifacts",
        "status",
    )
    missing = [key for key in required if key not in spec]
    if missing:
        raise OptimizationError("experiment missing fields: " + ", ".join(missing))
    experiment_id = _string(spec["experimentId"], "experimentId")
    if not experiment_id.startswith("s12-f-"):
        raise OptimizationError(f"invalid experiment ID: {experiment_id}")
    dimension = _string(spec["dimension"], "dimension")
    if dimension not in DIMENSIONS:
        raise OptimizationError(f"invalid experiment dimension: {dimension}")
    if spec["permittedSplit"] != "development":
        raise OptimizationError(f"experiment {experiment_id} is not development-only")
    for key in ("baselineConfigurationDigest", "candidateConfigurationDigest"):
        value = _string(spec[key], key)
        if not value.startswith("sha256:") or len(value) != 71:
            raise OptimizationError(f"invalid configuration digest: {experiment_id}")
    changed = spec["changedArtifacts"]
    if not isinstance(changed, list) or len(changed) != 1 or changed[0] != dimension:
        raise OptimizationError(
            f"experiment {experiment_id} changes more than one dimension"
        )
    preserved = spec["preservedArtifacts"]
    if not isinstance(preserved, list) or not set(REQUIRED_PRESERVED_ARTIFACTS) <= set(
        preserved
    ):
        raise OptimizationError(
            f"experiment {experiment_id} does not preserve governed artifacts"
        )
    metric_target = _object(spec["metricTarget"], f"{experiment_id}.metricTarget")
    if not metric_target:
        raise OptimizationError(f"experiment {experiment_id} has no metric target")
    _string(spec["stoppingRule"], f"{experiment_id}.stoppingRule")
    status = _string(spec["status"], f"{experiment_id}.status")
    if status not in {
        "REGISTERED",
        "NOT_EXECUTED_BASELINE_UNAVAILABLE",
        "EXECUTED",
        "REJECTED",
        "SELECTED",
    }:
        raise OptimizationError(f"invalid experiment status: {status}")


def validate_registry(registry: Mapping[str, object]) -> None:
    """Validate a registry envelope, uniqueness and no-test-split policy."""

    if registry.get("registryVersion") != REGISTRY_VERSION:
        raise OptimizationError("unknown experiment registry version")
    if registry.get("permittedSplits") != ["development"]:
        raise OptimizationError("registry permits a non-development split")
    experiments = registry.get("experiments")
    if not isinstance(experiments, list) or not experiments:
        raise OptimizationError("registry must contain experiments")
    ids: set[object] = set()
    for item in experiments:
        spec = _object(item, "experiment")
        if spec.get("experimentId") in ids:
            raise OptimizationError(
                f"duplicate experiment ID: {spec.get('experimentId')}"
            )
        ids.add(spec.get("experimentId"))
        validate_experiment(spec)


def compare_results(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    metric_target: Mapping[str, object],
) -> JsonObject:
    """Compare results only when both runs are real and hard invariants pass."""

    if baseline.get("status") != "SCORED" or candidate.get("status") != "SCORED":
        return {
            "status": "NOT_EXECUTED_BASELINE_UNAVAILABLE",
            "reason": "baseline and candidate must both be scored",
        }
    baseline_invariants = _object(
        baseline.get("hardInvariants"), "baseline.hardInvariants"
    )
    candidate_invariants = _object(
        candidate.get("hardInvariants"), "candidate.hardInvariants"
    )
    invariant_result = hard_invariant_regression(
        baseline_invariants, candidate_invariants
    )
    if invariant_result["status"] != "PASS":
        return {"status": "REJECTED_HARD_INVARIANT", "hardInvariants": invariant_result}
    baseline_metrics = _object(baseline.get("metrics"), "baseline.metrics")
    candidate_metrics = _object(candidate.get("metrics"), "candidate.metrics")
    deltas: JsonObject = {}
    passes = True
    for name, target in metric_target.items():
        direction = (
            str(target.get("direction", "higher"))
            if isinstance(target, dict)
            else "higher"
        )
        minimum = (
            float(target.get("minimumDelta", 0.0)) if isinstance(target, dict) else 0.0
        )
        before = float(baseline_metrics.get(name, 0.0))
        after = float(candidate_metrics.get(name, 0.0))
        delta = after - before
        deltas[name] = {
            "baseline": before,
            "candidate": after,
            "delta": delta,
            "target": minimum,
            "direction": direction,
        }
        passes = passes and (
            delta >= minimum if direction == "higher" else delta <= -minimum
        )
    return {
        "status": "PASS" if passes else "REJECTED_METRIC_TARGET",
        "deltas": deltas,
        "hardInvariants": invariant_result,
    }


def hard_invariant_regression(
    baseline: Mapping[str, object], candidate: Mapping[str, object]
) -> JsonObject:
    """Reject any candidate that weakens a named hard invariant."""

    names = set(baseline) | set(candidate)
    failures = [
        name
        for name in sorted(names)
        if baseline.get(name) is True and candidate.get(name) is not True
    ]
    return {
        "status": "PASS" if not failures else "FAIL",
        "regressions": failures,
        "checked": sorted(names),
    }


def select_candidate(comparisons: Mapping[str, Mapping[str, object]]) -> JsonObject:
    """Select exactly one passing development candidate, or select none."""

    passing = [
        experiment_id
        for experiment_id, comparison in comparisons.items()
        if comparison.get("status") == "PASS"
    ]
    if len(passing) != 1:
        return {
            "status": "NO_SELECTION",
            "reason": "multi-metric rule requires exactly one passing candidate",
            "passingExperiments": passing,
            "heldOutInspected": False,
        }
    return {"status": "SELECTED", "experimentId": passing[0], "heldOutInspected": False}


def freeze_candidate(
    selection: Mapping[str, object], spec: Mapping[str, object]
) -> JsonObject:
    """Bind a selected candidate; refuse to freeze an unselected or unexecuted one."""

    if selection.get("status") != "SELECTED" or selection.get(
        "experimentId"
    ) != spec.get("experimentId"):
        return {"status": "NOT_FROZEN", "reason": "candidate was not selected"}
    if spec.get("status") != "SELECTED":
        return {
            "status": "NOT_FROZEN",
            "reason": "candidate experiment is not marked selected",
        }
    return {
        "status": "FROZEN",
        "experimentId": spec["experimentId"],
        "configurationDigest": spec["candidateConfigurationDigest"],
        "registryDigest": digest(spec),
    }


def build_default_registry(baseline_report: Mapping[str, object]) -> JsonObject:
    """Create the five controlled experiment records for the approved boundary."""

    baseline_digest = _string(
        baseline_report.get("configurationDigest"), "baseline configurationDigest"
    )
    dataset_digest = _string(
        baseline_report.get("manifestDigest"), "baseline manifestDigest"
    )
    experiments: list[JsonObject] = []
    for number, dimension in enumerate(DIMENSIONS, start=1):
        candidate_config = {
            "release": "v0.6.0",
            "dimension": dimension,
            "experiment": f"s12-f-{number:02d}",
            "baselineConfigurationDigest": baseline_digest,
            "datasetManifestDigest": dataset_digest,
        }
        experiments.append(
            {
                "experimentId": f"s12-f-{number:02d}",
                "hypothesis": f"A bounded {dimension} change improves the registered development metric without weakening hard invariants.",
                "dimension": dimension,
                "permittedSplit": "development",
                "baselineConfigurationDigest": baseline_digest,
                "candidateConfigurationDigest": digest(candidate_config),
                "metricTarget": {
                    "semanticQuality": {"direction": "higher", "minimumDelta": 0.01}
                },
                "stoppingRule": "Stop after one development run or immediately on a hard-invariant regression.",
                "changedArtifacts": [dimension],
                "preservedArtifacts": list(REQUIRED_PRESERVED_ARTIFACTS),
                "datasetManifestDigest": dataset_digest,
                "status": "NOT_EXECUTED_BASELINE_UNAVAILABLE",
            }
        )
    registry: JsonObject = {
        "registryVersion": REGISTRY_VERSION,
        "status": "G5_PREPARATION_BLOCKED_BASELINE_UNAVAILABLE",
        "evaluatorVersion": EVALUATOR_VERSION,
        "permittedSplits": ["development"],
        "heldOutInspected": False,
        "experiments": experiments,
    }
    validate_registry(registry)
    registry["registryDigest"] = digest(registry)
    return registry


def build_g5_packet(
    registry: Mapping[str, object], baseline_report: Mapping[str, object]
) -> JsonObject:
    """Prepare G5 evidence without selecting a candidate from missing runs."""

    validate_registry(registry)
    baseline_status = baseline_report.get("status")
    comparisons = {
        str(_object(item, "experiment")["experimentId"]): {
            "status": "NOT_EXECUTED_BASELINE_UNAVAILABLE",
            "reason": "G4 baseline is not runtime-backed",
        }
        for item in cast(list[object], registry["experiments"])
    }
    selection = select_candidate(comparisons)
    return {
        "packetVersion": "s12.g5.packet.v1",
        "status": "G5_PREPARATION_BLOCKED_BASELINE_UNAVAILABLE",
        "registryVersion": registry["registryVersion"],
        "registryDigest": registry.get("registryDigest", digest(registry)),
        "baselineConfigurationDigest": baseline_report.get("configurationDigest"),
        "datasetManifestDigest": baseline_report.get("manifestDigest"),
        "baselineStatus": baseline_status,
        "experimentCount": len(comparisons),
        "comparisons": comparisons,
        "selection": selection,
        "hardInvariants": {"status": "NOT_EVALUATED_BASELINE_UNAVAILABLE"},
        "sliceMetrics": {},
        "costLatency": {"status": "NOT_AVAILABLE"},
        "heldOutInspected": False,
        "optimizationAuthorized": False,
        "rawSensitiveDataIncluded": False,
    }


def write_packet(packet: JsonObject, json_path: Path, markdown_path: Path) -> None:
    """Write G5 packet JSON and a concise human-readable summary."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Sprint 12 G5 Optimization Packet",
        "",
        f"**Status:** `{packet['status']}`",
        "",
        "The packet binds controlled development-only experiments to the approved",
        "G4 measurement boundary. No held-out data is inspected and no candidate",
        "is selected while the runtime-backed baseline is unavailable.",
        "",
        "## Bound evidence",
        "",
        f"- Registry: `{packet['registryVersion']}` / `{packet['registryDigest']}`",
        f"- Dataset manifest: `{packet['datasetManifestDigest']}`",
        f"- Baseline configuration: `{packet['baselineConfigurationDigest']}`",
        f"- Baseline status: `{packet['baselineStatus']}`",
        f"- Registered experiments: `{packet['experimentCount']}`",
        "",
        "## Measurement state",
        "",
        f"- Comparison state: `{packet['selection']['status']}`",
        f"- Hard invariants: `{packet['hardInvariants']['status']}`",
        f"- Held-out inspected: `{packet['heldOutInspected']}`",
        f"- Optimization authorized: `{packet['optimizationAuthorized']}`",
        "- Cost/latency and slice results: `NOT_AVAILABLE`",
        "",
        "## G5 acceptance checklist",
        "",
        "- [x] Registry requires hypothesis, development split, configuration",
        "  digests, metric target and stopping rule.",
        "- [x] Single-dimension change and preserved governance artifacts are",
        "  validated for prompt, context, agent-workflow, tool and model records.",
        "- [x] Candidate selection fails closed unless exactly one scored candidate",
        "  passes the multi-metric rule and hard invariants.",
        "- [x] Candidate freeze binds experiment, configuration and registry digests.",
        "- [x] Draft G5 packet is prepared.",
        "- [ ] Baseline-backed experiments are executed.",
        "- [ ] Candidate is evaluated on validation after development selection.",
        "- [ ] Human reviewers approve one candidate or record no-go.",
        "",
        "## Approval boundary (S12-83)",
        "",
        "`PENDING_HUMAN_APPROVAL`; this packet authorizes no optimization and no",
        "held-out evaluation until the runtime-backed G4 baseline exists.",
        "",
    ]
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Generate the controlled registry and draft G5 packet."""

    root = Path(__file__).resolve().parents[1]
    baseline = json.loads(
        (root / "evaluation/sprint-12/baseline/baseline-report.v1.json").read_text(
            encoding="utf-8"
        )
    )
    registry = build_default_registry(baseline)
    optimization_dir = root / "evaluation/sprint-12/optimization"
    optimization_dir.mkdir(parents=True, exist_ok=True)
    (optimization_dir / "experiment-registry.v1.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    packet = build_g5_packet(registry, baseline)
    write_packet(
        packet,
        optimization_dir / "g5-packet.v1.json",
        root / "docs/sprint-plans/sprint-12/g5-optimization.md",
    )
    print(
        json.dumps(
            {
                "status": packet["status"],
                "experimentCount": packet["experimentCount"],
                "selection": packet["selection"]["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
