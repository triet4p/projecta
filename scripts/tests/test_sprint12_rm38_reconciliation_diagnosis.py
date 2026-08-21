from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v8 as v8  # noqa: E402
import s12_f12_rm38_reconciliation_diagnosis as rm38  # noqa: E402
from sprint12_f12_two_step_contracts_v5 import EntityCandidate, RelationCandidate  # noqa: E402


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm38_reproduces_first_case_predicted_entities_boundary_without_provider() -> None:
    reproduction = rm38.reproduce_failure()
    assert reproduction["caseId"] == "s12-a-4003"
    assert reproduction["arm"] == "predicted-entities"
    assert reproduction["mockProviderCalls"] == 0
    assert reproduction["armMaterializerInvalidEvidenceCount"] == 0
    assert reproduction["diagnosticFailureTotal"] == 1
    assert reproduction["diagnosticReasonCounts"]["trigger_quote_missing"] == 1
    assert reproduction["exception"] == (
        "evidence reason counts do not reconcile with arm materializer failures"
    )


def test_rm38_diagnosis_keeps_historical_custody_and_locks() -> None:
    diagnosis, proposal = rm38.build_artifacts()
    assert diagnosis["sourceBoundary"]["providerCalls"] == 0
    assert diagnosis["sourceBoundary"]["rawProviderPayloadInspected"] is False
    assert diagnosis["sourceBoundary"]["historicalV6Report"]["digest"] == rm38.REPORT_V6_DIGEST
    assert _digest(rm38.REPORT_V6) == rm38.REPORT_V6_DIGEST
    assert diagnosis["governance"]["providerExecutionAuthorized"] is False
    assert diagnosis["governance"]["supersedingLineagePreparationAuthorized"] is False
    assert proposal["governance"]["runtimeImplementationAuthorized"] is False


def test_rm38_endpoint_projection_gap_is_visible_and_fail_closed() -> None:
    case = rm38._load_first_case()
    relation = RelationCandidate("answers", "entity-01", "entity-02", Decimal("1"), 0, 82, "answers")
    predicted = (
        EntityCandidate("entity-01", "Task", 0, 21, Decimal("1")),
        EntityCandidate("entity-02", "Risk", 29, 43, Decimal("1")),
    )
    reasons = v8._evidence_reasons(case, (relation,), predicted, rm38._gold_table(case), False)
    assert reasons["materializer_detail_unavailable"] == 1


def test_rm38_artifact_files_match_generated_contract() -> None:
    rm38.write_artifacts()
    diagnosis = json.loads(rm38.DIAGNOSIS.read_text(encoding="utf-8"))
    proposal = json.loads(rm38.PROPOSAL.read_text(encoding="utf-8"))
    assert diagnosis["status"] == "OFFLINE_DIAGNOSIS_COMPLETE_PENDING_RM39_OWNER_REVIEW"
    assert proposal["status"] == "OFFLINE_REMEDIATION_PROPOSAL_PENDING_RM39_OWNER_REVIEW"
    assert diagnosis["reproduction"]["diagnosticFailureTotal"] == 1
    serialized = json.dumps(diagnosis)
    assert '"rawProviderPayload":' not in serialized
    assert '"rawSourceText":' not in serialized


@pytest.mark.parametrize(
    "field",
    ["providerExecutionAuthorized", "supersedingLineagePreparationAuthorized", "promotionAuthorized"],
)
def test_rm38_proposal_keeps_governance_field_closed(field: str) -> None:
    _, proposal = rm38.build_artifacts()
    assert proposal["governance"][field] is False
