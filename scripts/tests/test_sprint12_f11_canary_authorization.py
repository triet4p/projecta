"""Static lineage and zero-call guards for S12-f-11 canary authorization."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

import run_sprint12_f11_canary_v2 as canary

OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
AUTHORIZATION = OPTIMIZATION / "s12-f-11-canary-authorization.v1.json"
PACKAGE = OPTIMIZATION / "s12-f-11-canary-execution-package.v2.json"
FREEZE = OPTIMIZATION / "s12-f-11-canary-freeze.v2.json"
OUTPUT = OPTIMIZATION / "s12-f-11-canary-report.v2.json"
REVIEW = OPTIMIZATION / "s12-f-11-full-stage-a-review.v1.json"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _lf_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def test_authorization_binds_exact_v2_lineage_and_remains_canary_only() -> None:
    authorization = _read(AUTHORIZATION)
    freeze = _read(FREEZE)

    assert authorization["status"] == "APPROVED_FOR_DEVELOPMENT_CANARY"
    assert authorization["executionPackage"]["digest"] == _digest(PACKAGE)
    assert authorization["freezeRecord"]["digest"] == _digest(FREEZE)
    assert freeze["executionPackageDigest"] == _lf_digest(PACKAGE)
    assert authorization["commitSha"] == freeze["commitSha"] == "ed08f99"
    assert subprocess.run(
        ("git", "merge-base", "--is-ancestor", "ed08f99", "HEAD"),
        cwd=ROOT,
        check=False,
        capture_output=True,
    ).returncode == 0
    assert authorization["providerExecutionAuthorized"] is True
    assert authorization["providerCalls"] == 4
    assert authorization["requiredSchemaValidResponses"] == 4
    assert authorization["retryPolicy"] == "none"
    assert authorization["stageBAuthorized"] is False
    assert authorization["candidateSelectionAuthorized"] is False
    assert authorization["promotionAuthorized"] is False
    assert authorization["fullStageAAuthorized"] is False
    assert authorization["providerCallsPerformedAtIssuance"] is False
    assert authorization["canaryExecutedAtIssuance"] is False
    assert OUTPUT.exists()
    report = _read(OUTPUT)
    assert report["providerCallsAttempted"] == 4
    assert report["schemaValidResponses"] == 4
    assert report["usageValidResponses"] == 4
    assert report["providerCallsPriced"] == 4
    assert report["retryCount"] == 0
    assert report["heldOutInspected"] is False
    assert report["stageBAuthorized"] is False


class _NoCallTransport:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, **_kwargs: object) -> dict[str, object]:
        self.calls += 1
        raise AssertionError("transport must remain unused for invalid authorization")


def test_invalid_authorization_fails_before_transport(tmp_path: Path) -> None:
    transport = _NoCallTransport()
    adapter = canary.build_canary_adapter(
        {
            "PROJECTA_LLM_TYPE": "openai-response",
            "PROJECTA_LLM_BASE_URL": "https://mock.invalid",
            "PROJECTA_LLM_API_KEY": "test-only",
            "PROJECTA_LLM_MODEL": "deepseek-v4-flash",
        },
        transport=transport,
    )
    invalid = _read(AUTHORIZATION)
    invalid["status"] = "WITHHELD"
    invalid["runtimeConfiguration"]["digest"] = adapter.runtime_configuration_digest
    invalid_path = tmp_path / "invalid-authorization.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(canary.CanaryExecutionError, match="not approved"):
        canary.run_canary(
            provider_adapter=adapter,
            authorization_path=invalid_path,
            output_path=tmp_path / "report.json",
        )
    assert transport.calls == 0


def test_post_canary_review_opens_preparation_only() -> None:
    review = _read(REVIEW)
    committed_report = subprocess.check_output(
        (
            "git",
            "show",
            (
                "f25ede8:evaluation/sprint-12/optimization/"
                "s12-f-11-canary-report.v2.json"
            ),
        ),
        cwd=ROOT,
    )
    committed_digest = "sha256:" + hashlib.sha256(committed_report).hexdigest()

    assert review["status"] == "APPROVED_TO_PREPARE_FULL_STAGE_A_PACKAGE"
    assert (
        review["decisionBasis"]["canaryReport"]["committedBlobDigest"]
        == committed_digest
    )
    assert review["reviewConclusion"]["fullStageAPackageAvailable"] is False
    assert review["reviewConclusion"]["fullStageAAuthorizationIssued"] is False
    assert review["reviewConclusion"]["providerExecutionAuthorized"] is False
    assert review["governance"]["canaryAuthorizationReusable"] is False
    assert review["governance"]["stageBAuthorized"] is False
    assert review["requiredFullStageAPackage"]["sharedProviderCalls"] == 48
    assert review["requiredFullStageAPackage"]["branchOutputs"] == 96
