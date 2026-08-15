"""Run the versioned m3.v2 contract candidate on a bounded development subset."""

import argparse
import hashlib
import json
import statistics
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import sprint12_evaluator as evaluator

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = (
    ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-development.v1.json"
)
TARGET_SLICES = (
    "contradiction-or-supersession",
    "duplicate-evidence",
    "temporal-change",
    "unicode-and-noisy-text",
)
CASES_PER_SLICE = 8
DEFAULT_ATOMIC_PATH = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v1.json"
DEFAULT_SCENARIO_PATH = ROOT / "evaluation/sprint-12/corpus/scenario-development-validation.v1.json"
DEFAULT_MANIFEST_PATH = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v1.json"


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _select_cases(
    loaded: evaluator.LoadedDataset,
    target_slices: tuple[str, ...] = TARGET_SLICES,
    cases_per_slice: int = CASES_PER_SLICE,
) -> list[dict[str, evaluator.JSONValue]]:
    by_slice: dict[str, list[dict[str, evaluator.JSONValue]]] = {
        slice_name: [] for slice_name in target_slices
    }
    for case in loaded.cases:
        if case.get("split") != "development":
            continue
        case_id = str(case["caseId"])
        manifest_item = next(
            item for item in loaded.manifest["atomicCases"] if item["caseId"] == case_id
        )
        slice_name = str(manifest_item.get("slice", "unknown"))
        if slice_name in by_slice:
            by_slice[slice_name].append(case)
    selected: list[dict[str, evaluator.JSONValue]] = []
    for slice_name in target_slices:
        selected.extend(
            sorted(by_slice[slice_name], key=lambda item: str(item["caseId"]))[
                :cases_per_slice
            ]
        )
    return selected


def _select_case_ids(
    loaded: evaluator.LoadedDataset, case_ids: tuple[str, ...]
) -> list[dict[str, evaluator.JSONValue]]:
    by_id = {str(case["caseId"]): case for case in loaded.cases}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise ValueError("requested case IDs are absent: " + ", ".join(missing))
    selected = [by_id[case_id] for case_id in case_ids]
    if any(case.get("split") != "development" for case in selected):
        raise ValueError("candidate subset must remain development-only")
    return selected


def _aggregate_metrics(case_results: dict[str, dict[str, object]]) -> dict[str, float]:
    """Expose scorer-derived development metrics without counting failures."""

    scored = [item for item in case_results.values() if item.get("status") == "scored"]

    def mean(name: str) -> float:
        values = [
            float(item[name])
            for item in scored
            if isinstance(item.get(name), (int, float))
        ]
        return statistics.fmean(values) if values else 0.0

    def nested_mean(group: str, name: str) -> float:
        values = [
            float(item[group][name])
            for item in scored
            if isinstance(item.get(group), dict)
            and isinstance(item[group].get(name), (int, float))
        ]
        return statistics.fmean(values) if values else 0.0

    return {
        "entityMacroF1": nested_mean("entities", "f1"),
        "relationMacroF1": nested_mean("relations", "f1"),
        "linkMacroF1": nested_mean("links", "f1"),
        "abstentionAccuracy": mean("abstentionAccuracy"),
        "hallucinationRate": mean("hallucinationRate"),
    }


def run_candidate(
    *,
    atomic_path: Path = DEFAULT_ATOMIC_PATH,
    scenario_path: Path = DEFAULT_SCENARIO_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    prompt_variant: str = "m3.prompt.v2",
    target_slices: tuple[str, ...] = TARGET_SLICES,
    cases_per_slice: int = CASES_PER_SLICE,
    case_ids: tuple[str, ...] | None = None,
    sampling_configuration: Mapping[str, object] | None = None,
    candidate_kind: str = "contract-alignment-evidence-materialization-and-local-relation-ids",
) -> dict[str, object]:
    loaded = evaluator.load_dataset(
        atomic_path,
        scenario_path,
        manifest_path,
    )
    cases = (
        _select_case_ids(loaded, case_ids)
        if case_ids is not None
        else _select_cases(loaded, target_slices, cases_per_slice)
    )
    subset = replace(loaded, cases=cases)
    case_results, operational, failures, config = evaluator._runtime_baseline(
        subset,
        dict(evaluator.os.environ),
        schema_version="m3.v2",
        operation_id="s12-g4.1-m3-v2-contract-candidate",
        profile_revision="contract-v2-candidate",
        prompt_variant=prompt_variant,
        sampling_configuration=sampling_configuration,
    )
    coverage = [
        {
            "caseId": case_id,
            "split": next(
                str(case["split"]) for case in cases if str(case["caseId"]) == case_id
            ),
            "status": result.get("status"),
        }
        for case_id, result in sorted(case_results.items())
    ]
    status = (
        "CANDIDATE_DEVELOPMENT_SCORED"
        if not failures
        else "CANDIDATE_DEVELOPMENT_WITH_FAILURES"
    )
    gold_positive_counts = {
        name: sum(
            len(case.get("gold", {}).get(name, []))
            for case in cases
            if isinstance(case.get("gold"), dict)
        )
        for name in ("entities", "relations", "links")
    }
    digest_map: dict[str, str] = {
        "evaluatorCode": _file_digest(ROOT / "scripts/sprint12_evaluator.py"),
        "candidateRunnerCode": _file_digest(Path(__file__)),
        "promptCode": _file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/prompt.py"
        ),
        "runtimeContractCode": _file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/contracts.py"
        ),
        "runtimeServiceCode": _file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/service.py"
        ),
        "manifest": subset.manifest.get("manifestDigest"),
    }
    prompt_artifact = config.get("promptArtifact")
    if isinstance(prompt_artifact, str):
        digest_map["promptArtifact"] = _file_digest(ROOT / prompt_artifact)

    result: dict[str, object] = {
        "schemaVersion": "s12.contract-candidate.v1",
        "status": status,
        "contractVersion": "m3.v2",
        "candidateKind": candidate_kind,
        "split": "development",
        "slices": list(target_slices),
        "casesPerSlice": cases_per_slice,
        "caseCount": len(cases),
        "datasetVersion": subset.dataset.get("datasetVersion"),
        "caseCoverage": coverage,
        "omittedCaseCount": len(cases) - len(coverage),
        "missingOutputCount": sum(
            1 for item in coverage if item["status"] == "missing-output"
        ),
        "failureCount": len(failures),
        "goldPositiveCounts": gold_positive_counts,
        "metrics": {
            **_aggregate_metrics(case_results),
            "perCase": case_results,
        },
        "operational": evaluator.score_operational(operational),
        "operationalRecords": operational,
        "failures": failures,
        "hardInvariants": {
            "status": "PASS" if not failures else "FAIL",
            "schemaValidity": not failures,
            "relationContractRepresentable": not any(
                item.get("failureClass") == "cross_project_link" for item in failures
            ),
            "splitIntegrity": all(item["split"] == "development" for item in coverage),
            "datasetDigestBinding": True,
            "heldOutNonLeakage": True,
        },
        "configuration": config,
        "digests": {
            **digest_map,
            "schemaContract": evaluator.digest(
                {
                    "schemaVersion": "m3.v2",
                    "runtimeServiceCode": _file_digest(
                        ROOT / "apps/api/src/projecta_api/extraction/service.py"
                    ),
                    "runtimeContractCode": _file_digest(
                        ROOT / "apps/api/src/projecta_api/extraction/contracts.py"
                    ),
                }
            ),
            "modelConfiguration": evaluator.digest(
                {
                    "model": config.get("model"),
                    "baseUrl": config.get("baseUrl"),
                    "schemaVersion": config.get("schemaVersion"),
                    "promptVersion": config.get("promptVersion"),
                    "sampling": config.get("samplingConfiguration"),
                }
            ),
        },
        "datasetManifestDigest": subset.manifest.get("manifestDigest"),
        "baselineLockDigest": "sha256:"
        + hashlib.sha256(
            (ROOT / "evaluation/sprint-12/baseline/baseline-lock.v1.json").read_bytes()
        ).hexdigest(),
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "heldOutInspected": False,
        "validationAuthorized": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atomic-path", type=Path, default=DEFAULT_ATOMIC_PATH)
    parser.add_argument("--scenario-path", type=Path, default=DEFAULT_SCENARIO_PATH)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--prompt-variant", default="m3.prompt.v2")
    parser.add_argument("--slices", nargs="+", default=list(TARGET_SLICES))
    parser.add_argument("--cases-per-slice", type=int, default=CASES_PER_SLICE)
    parser.add_argument("--case-ids", nargs="+", default=None)
    parser.add_argument(
        "--candidate-kind",
        default="contract-alignment-evidence-materialization-and-local-relation-ids",
    )
    args = parser.parse_args()
    result = run_candidate(
        atomic_path=args.atomic_path,
        scenario_path=args.scenario_path,
        manifest_path=args.manifest_path,
        prompt_variant=args.prompt_variant,
        target_slices=tuple(args.slices),
        cases_per_slice=args.cases_per_slice,
        case_ids=tuple(args.case_ids) if args.case_ids else None,
        candidate_kind=args.candidate_kind,
    )
    args.output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "caseCount": result["caseCount"],
                "missingOutputCount": result["missingOutputCount"],
                "failureCount": result["failureCount"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
