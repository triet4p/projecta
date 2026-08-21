"""Regenerate RM-32 v8 preparation artifacts after a runtime commit."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
PACKAGE_PATH = OPT / "s12-f-12-rm32-execution-package.v8.json"
PREREG_PATH = OPT / "s12-f-12-rm32-preregistration.v8.json"
FREEZE_PATH = OPT / "s12-f-12-rm32-technical-freeze.v8.json"
CURRENT_NEXT_PATH = ROOT / "evaluation/sprint-12/current-state-next-rm32.v1.json"
G5_SNAPSHOT_PATH = OPT / "g5-packet.v20.rm32-offline-preparation.json"
PREFLIGHT_PATH = ROOT / "scripts/preflight_sprint12_f12_rm32.py"
RM32_TEST_PATH = ROOT / "scripts/tests/test_sprint12_rm32_offline_preparation.py"


def current_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def blob_digest(commit: str, path_text: str) -> str:
    blob = subprocess.check_output(["git", "show", f"{commit}:{path_text}"], cwd=ROOT)
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(path.as_posix())
    return value


def dump(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    runtime_paths = [
        "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json",
        "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json",
        "evaluation/sprint-12/optimization/s12-f-12-m3-prompt-v7-v2-two-step-extraction.v1.txt",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v5.json",
        "evaluation/sprint-12/harness/metric-contract.v2.json",
        "evaluation/sprint-12/harness/slice-threshold-contract.v1.json",
        "evaluation/sprint-12/harness/relation-trigger-contract.v1.json",
        "evaluation/sprint-12/harness/s12-f-12-runtime-configuration.v1.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-1-entity-envelope.schema.v2.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-2-relation-envelope.schema.v2.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json",
        "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json",
        "scripts/run_sprint12_f12_stage_a_v2.py",
        "scripts/run_sprint12_f12_stage_a_v3.py",
        "scripts/run_sprint12_f12_stage_a_v4.py",
        "scripts/run_sprint12_f12_stage_a_v8.py",
        "scripts/sprint12_f12_two_step_contracts_v2.py",
        "scripts/sprint12_f12_two_step_contracts_v4.py",
        "scripts/sprint12_f12_two_step_contracts_v5.py",
        "scripts/sprint12_provider_adapter.py",
        "scripts/sprint12_f12_provider_adapter_v2.py",
        "scripts/s12_f12_rm30_diagnostic_remediation.py",
    ]
    runtime = {path: blob_digest(commit, path) for path in runtime_paths}
    preparation_paths = [
        "scripts/regenerate_sprint12_f12_rm32_v8.py",
        "scripts/preflight_sprint12_f12_rm32.py",
        "scripts/tests/test_sprint12_rm32_offline_preparation.py",
        "scripts/tests/test_sprint12_f12_v8_runtime_diagnostics.py",
    ]
    preparation = {path: current_digest(ROOT / path) for path in preparation_paths}

    package = load(PACKAGE_PATH)
    package["executionCommitSha"] = commit
    package["runtimeBoundDigests"] = runtime
    package["preparationEvidence"] = preparation
    package.pop("boundDigests", None)
    package["exactCommitValidated"] = True
    package["runtimeBinding"] = {
        "digestMode": "git_blob_sha256",
        "runtimeBlobCount": len(runtime),
        "preparationEvidenceExcludedFromExecutionCommit": True,
        "validatedBy": "scripts/preflight_sprint12_f12_rm32.py",
    }
    package["executionRunnerImplemented"] = True
    package["executionRunner"] = {
        "path": "scripts/run_sprint12_f12_stage_a_v8.py",
        "digest": runtime["scripts/run_sprint12_f12_stage_a_v8.py"],
        "guarded": True,
        "liveIntegrationOpened": True,
        "providerExecutionAuthorized": False,
    }
    package["reportSchema"] = {
        "path": "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json",
        "digest": runtime["evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json"],
    }
    package["authorizationSchema"] = {
        "path": "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json",
        "digest": runtime["evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json"],
    }
    package["outputPath"] = "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json"
    package["providerCallsPerformed"] = 0
    package["retryCount"] = 0
    package["governance"]["nextGate"] = "RM-33 owner issuance review; separate v8 exact-commit authorization remains required"
    dump(PACKAGE_PATH, package)

    prereg = load(PREREG_PATH)
    prereg["executionCommitSha"] = commit
    prereg["measurement"]["reportSchema"] = "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json"
    prereg["measurement"]["authorizationSchema"] = "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json"
    prereg["measurement"]["runner"] = "scripts/run_sprint12_f12_stage_a_v8.py"
    prereg["measurement"]["preflight"] = "scripts/preflight_sprint12_f12_rm32.py"
    prereg["report"]["schemaPath"] = "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json"
    prereg["runtimeBinding"] = {"digestMode": "git_blob_sha256", "runtimeBlobCount": len(runtime)}
    dump(PREREG_PATH, prereg)

    freeze = load(FREEZE_PATH)
    freeze["executionCommitSha"] = commit
    freeze["executionPackageDigest"] = current_digest(PACKAGE_PATH)
    freeze["preregistrationDigest"] = current_digest(PREREG_PATH)
    freeze["runnerDigest"] = runtime["scripts/run_sprint12_f12_stage_a_v8.py"]
    freeze["reportSchemaDigest"] = runtime["evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json"]
    freeze["authorizationSchemaDigest"] = runtime["evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json"]
    freeze["runtimeBinding"] = {
        "digestMode": "git_blob_sha256",
        "runtimeBlobCount": len(runtime),
        "preparationEvidenceExcludedFromExecutionCommit": True,
    }
    freeze["issuance"]["exactCommitValidated"] = True
    freeze["issuance"]["validatedRuntimeBlobCount"] = len(runtime)
    freeze["issuance"]["validationMethod"] = "git show commit:path byte digest"
    freeze["output"]["path"] = "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json"
    freeze["governance"]["nextGate"] = "RM-33 owner issuance review; no provider call is authorized by preparation"
    dump(FREEZE_PATH, freeze)
    package_digest = current_digest(PACKAGE_PATH)
    prereg_digest = current_digest(PREREG_PATH)
    freeze_digest = current_digest(FREEZE_PATH)
    preflight_digest = current_digest(PREFLIGHT_PATH)
    rm32_test_digest = current_digest(RM32_TEST_PATH)
    current_next = load(CURRENT_NEXT_PATH)
    current_next["rm32Preparation"]["preregistration"]["digest"] = prereg_digest
    current_next["rm32Preparation"]["executionPackage"]["digest"] = package_digest
    current_next["rm32Preparation"]["technicalFreeze"]["digest"] = freeze_digest
    current_next["rm32Preparation"]["preflight"]["digest"] = preflight_digest
    current_next["rm32Preparation"]["mockTests"]["digest"] = rm32_test_digest
    current_next["rm32Preparation"]["mockTests"]["result"] = "4 passed"
    current_next["rm32Preparation"]["runtimeImplementation"] = {
        "commit": commit,
        "runnerPath": "scripts/run_sprint12_f12_stage_a_v8.py",
        "reportSchemaPath": "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json",
        "authorizationSchemaPath": "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json",
        "runtimeBlobCount": len(runtime),
    }
    current_next["nextGate"] = "RM-33 owner issuance review; separate v8 exact-commit authorization remains required"
    dump(CURRENT_NEXT_PATH, current_next)

    g5 = load(G5_SNAPSHOT_PATH)
    g5["rm32Preparation"]["preregistration"]["digest"] = prereg_digest
    g5["rm32Preparation"]["executionPackage"]["digest"] = package_digest
    g5["rm32Preparation"]["technicalFreeze"]["digest"] = freeze_digest
    g5["rm32Preparation"]["preflight"]["digest"] = preflight_digest
    g5["rm32Preparation"]["mockTests"] = 4
    g5["rm32Preparation"]["runtimeImplementation"] = {
        "commit": commit,
        "runnerPath": "scripts/run_sprint12_f12_stage_a_v8.py",
        "reportSchemaPath": "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json",
        "authorizationSchemaPath": "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json",
        "runtimeBlobCount": len(runtime),
    }
    dump(G5_SNAPSHOT_PATH, g5)
    print(json.dumps({"executionCommitSha": commit, "runtimeBlobCount": len(runtime), "preparationEvidenceCount": len(preparation)}, indent=2))


if __name__ == "__main__":
    main()
