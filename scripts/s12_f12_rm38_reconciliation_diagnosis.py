"""RM-38 offline diagnosis for the RM-36 first-case reconciliation failure.

This module uses one repository-visible frozen case and deterministic mock
objects.  It never calls a provider, reads a provider payload, or writes to a
runtime report path.  The generated artifacts contain only sanitized counts
and code-path facts.
"""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v4 as v4
import run_sprint12_f12_stage_a_v8 as v8
from sprint12_f12_two_step_contracts_v5 import EntityCandidate, RelationCandidate
from sprint12_provider_adapter import ProviderCapture

RM36 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm36-execution-transition.v1.json"
RM37 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm37-decision-transition.v1.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
CORPUS = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
DIAGNOSIS = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm38-reconciliation-diagnosis.v1.json"
PROPOSAL = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm38-remediation-proposal.v1.json"

REPORT_V6_DIGEST = "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
FIRST_CASE_ID = "s12-a-4003"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_first_case() -> dict[str, Any]:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    return next(case for case in corpus["cases"] if case["caseId"] == FIRST_CASE_ID)


def _gold_table(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "candidateId": item["id"],
            "type": item["type"],
            "startOffset": item["span"]["start"],
            "endOffset": item["span"]["end"],
            "confidence": 1.0,
        }
        for item in case["gold"]["entities"]
    ]


def _mock_stage2_capture() -> ProviderCapture:
    return ProviderCapture(
        payload={
            "schemaVersion": "s12-f-12.stage2.relation-envelope.v2",
            "relations": [],
            "abstention": {"required": False, "reason": None},
        },
        usage={"promptCacheHitTokens": 0, "promptCacheMissTokens": 1, "outputTokens": 1},
        retry_count=0,
    )


def reproduce_failure() -> dict[str, Any]:
    """Reproduce the same v8 exception with a sanitized non-exact mock.

    The mock deliberately has one semantically wrong relation and no trigger
    quote.  The historical provider payload is unavailable, so this proves the
    deterministic code-path defect, not the hidden payload's exact contents.
    """

    case = _load_first_case()
    predicted = (
        EntityCandidate("entity-01", "Task", 0, 21, Decimal("1")),
        EntityCandidate("entity-02", "Risk", 29, 43, Decimal("1")),
    )
    # Gold predicate is ``answers``.  ``supports`` is a valid relation object
    # but is semantically non-exact; trigger_quote=None is an invalid evidence
    # condition that the old diagnostic loop nevertheless counts.
    non_exact_relation = RelationCandidate(
        "supports", "entity-01", "entity-02", Decimal("1"), 0, 82, None
    )
    kwargs = {
        "stage1": None,
        "stage1_failure": None,
        "predicted_entities": predicted,
        "stage2": _mock_stage2_capture(),
        "stage2_failure": None,
        "relations": (non_exact_relation,),
        "abstention": False,
        "gold_candidates": _gold_table(case),
        "is_gold_arm": False,
    }
    base = v4._arm_record(case, **kwargs)
    v8._PENDING_SCHEMA_REASONS.clear()
    reasons = v8._evidence_reasons(case, kwargs["relations"], predicted, kwargs["gold_candidates"], False)
    raised: str | None = None
    try:
        v8._arm_record_v8(case, **kwargs)
    except v8.F12StageAV8Error as error:
        raised = str(error)
    if raised != "evidence reason counts do not reconcile with arm materializer failures":
        raise AssertionError(f"RM-38 reproducer did not hit the recorded boundary: {raised!r}")
    return {
        "caseId": FIRST_CASE_ID,
        "arm": "predicted-entities",
        "capturesBeforeFailure": ["stage1:predicted-entities", "stage2:predicted-entities", "stage2:gold-entities"],
        "mockProviderCalls": 0,
        "mockRelationCount": 1,
        "mockSemanticPairing": {"exactMatch": 0, "nonExactRelation": 1, "evidenceApplicable": 0},
        "armMaterializerInvalidEvidenceCount": int(base["relation"]["invalidEvidenceCount"]),
        "diagnosticReasonCounts": reasons,
        "diagnosticFailureTotal": sum(reasons.values()),
        "exception": raised,
        "endpointSpanShapeObservedByOldLoop": "(start,end,type) passed to a (start,end)-only classifier",
    }


def build_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    reproduction = reproduce_failure()
    diagnosis = {
        "artifactVersion": "s12.s12-f-12.rm38-reconciliation-diagnosis.v1",
        "status": "OFFLINE_DIAGNOSIS_COMPLETE_PENDING_RM39_OWNER_REVIEW",
        "experimentId": "s12-f-12",
        "taskId": "S12-RM-38",
        "diagnosisDate": "2026-08-22",
        "sourceBoundary": {
            "rm36ExecutionTransition": {"path": RM36.relative_to(ROOT).as_posix(), "digest": digest(RM36)},
            "rm37DecisionTransition": {"path": RM37.relative_to(ROOT).as_posix(), "digest": digest(RM37)},
            "historicalV6Report": {"path": REPORT_V6.relative_to(ROOT).as_posix(), "digest": REPORT_V6_DIGEST},
            "rawProviderPayloadInspected": False,
            "rawSourceTextPersisted": False,
            "providerCalls": 0,
        },
        "reproduction": reproduction,
        "rootCause": {
            "primary": "_arm_record_v8 derives armMaterializerInvalidEvidenceCount from score_relations evidence buckets, which apply only to semantically exact pairs; _evidence_reasons iterates every predicted relation, including non-exact and extra relations.",
            "divergence": "A non-exact relation contributes 0 to invalidEvidenceCount but contributes 1 diagnostic reason when its evidence is missing or unsupported.",
            "secondary": "_entity_spans returns (start,end,type) triples while diagnose_evidence_failure accepts only (start,end); this can degrade a valid finite reason to materializer_detail_unavailable.",
            "historicalAttributionBoundary": "The RM-36 payload was not retained. The mock proves the code defect and matching exception, but does not claim the hidden provider relation took this exact semantic branch.",
        },
        "impact": {
            "failureBoundary": "first_case_predicted_entities_arm_diagnostic_reconciliation",
            "callsAttemptedBeforeHistoricalFailure": 3,
            "reportPersisted": False,
            "accountingComplete": False,
            "retryOrRerun": False,
            "authorizationSpent": True,
            "qualityResultAvailable": False,
        },
        "earlierTestGap": {
            "missedBecause": "Existing deterministic diagnostics used an exact relation with missing evidence, so both counters were 1; they did not include a non-exact relation with invalid evidence.",
            "newRegressionRequired": "Cover exact-invalid, non-exact-invalid, extra-invalid and endpoint span projection cases separately.",
        },
        "governance": {
            "offlineDiagnosisPreparationAuthorized": True,
            "offlineRemediationPreparationAuthorized": True,
            "providerExecutionAuthorized": False,
            "rerunAuthorized": False,
            "retryAuthorized": False,
            "supersedingLineagePreparationAuthorized": False,
            "preregistrationIssued": False,
            "technicalFreezeIssued": False,
            "validationAccessAuthorized": False,
            "heldOutAccessAuthorized": False,
            "stageBAuthorized": False,
            "candidateSelectionAuthorized": False,
            "promotionAuthorized": False,
            "nextOwnerGate": "S12-RM-39_OWNER_REVIEW_RM38_DIAGNOSIS_AND_REMEDIATION_PROPOSAL",
        },
    }
    proposal = {
        "artifactVersion": "s12.s12-f-12.rm38-remediation-proposal.v1",
        "status": "OFFLINE_REMEDIATION_PROPOSAL_PENDING_RM39_OWNER_REVIEW",
        "experimentId": "s12-f-12",
        "taskId": "S12-RM-38",
        "diagnosisPath": DIAGNOSIS.relative_to(ROOT).as_posix(),
        "implementationScope": {
            "authorizedNow": "offline proposal and deterministic regression design only",
            "notAuthorizedNow": ["runtime implementation", "provider execution", "retry", "rerun", "superseding lineage", "issuance", "validation", "held-out", "Stage B", "selection", "promotion"],
        },
        "finiteRemediation": {
            "pairingRule": "derive diagnostic candidates from the exact semantic pairs used by score_relations; never diagnose nonApplicable, wrong, extra or missing semantic relations against the arm invalid-evidence total",
            "endpointRule": "project entity spans to two-tuples (start,end) before calling diagnose_evidence_failure",
            "reconciliationRule": "sum finite reason counts exactly equals unsupported+missing for the same exact semantic pair set",
            "failClosedRule": "unknown or malformed runtime detail maps to materializer_detail_unavailable and never passes reconciliation by omission",
        },
        "acceptanceTests": [
            "exact semantic match with missing evidence counts once",
            "non-exact relation with invalid evidence does not inflate arm invalidEvidence",
            "extra relation with invalid evidence does not inflate arm invalidEvidence",
            "three-tuple entity metadata is projected to a two-tuple classifier span",
            "historical RM-36 transition and v6 digest remain unchanged",
            "no provider adapter is instantiated or called",
        ],
        "governance": {
            "providerExecutionAuthorized": False,
            "runtimeImplementationAuthorized": False,
            "supersedingLineagePreparationAuthorized": False,
            "newAuthorizationIssued": False,
            "validationAccessAuthorized": False,
            "heldOutAccessAuthorized": False,
            "stageBAuthorized": False,
            "candidateSelectionAuthorized": False,
            "promotionAuthorized": False,
        },
    }
    return diagnosis, proposal


def write_artifacts() -> None:
    diagnosis, proposal = build_artifacts()
    DIAGNOSIS.write_text(json.dumps(diagnosis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PROPOSAL.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_artifacts()
    print(DIAGNOSIS)
    print(PROPOSAL)
