from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from s12_f12_rm28_offline_diagnostics import (  # noqa: E402
    REPORT_DIGEST,
    build_from_immutable_report,
    digest,
)
from sprint12_f12_two_step_contracts_v5 import (  # noqa: E402
    ContractViolation,
    EntityCandidate,
    RelationCandidate,
    materialize_evidence_context,
    score_relations,
    validate_stage1_response,
    validate_stage2_response,
)


REPORT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm28-offline-remediation.v1.json"
CONTRACT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm28-diagnostic-contract.v1.json"


def test_rm28_report_digest_and_findings_are_recomputed_without_provider() -> None:
    artifact = build_from_immutable_report()
    assert digest(REPORT) == REPORT_DIGEST
    assert artifact["sourceEvidence"]["providerCallsAttempted"] == 144
    assert artifact["sourceEvidence"]["retryCount"] == 0
    assert artifact["provenFindings"]["schemaInvalidTotal"] == 6
    assert artifact["provenFindings"]["schemaInvalidByArmStage"] == {
        "predicted-entities:stage1": 5,
        "gold-entities:stage2": 1,
    }
    assert artifact["provenFindings"]["invalidEvidenceTotal"] == 17
    assert artifact["provenFindings"]["invalidEvidence"]["bucketTotals"]["unsupported"] == 17
    assert artifact["provenFindings"]["goldRelationsControlInvalidEvidence"] == 0
    assert artifact["governance"]["providerExecutionAuthorized"] is False


def test_rm28_artifact_binds_immutable_report_and_offline_contract() -> None:
    artifact = json.loads(PACKAGE.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert artifact["sourceEvidence"]["digest"] == REPORT_DIGEST
    assert artifact["offlineRemediation"]["diagnosticContract"]["path"].endswith(
        "s12-f-12-rm28-diagnostic-contract.v1.json"
    )
    assert contract["inputPolicy"]["providerCalls"] == 0
    assert contract["governance"]["providerExecutionAuthorized"] is False
    assert contract["inputPolicy"]["rawProviderPayloadAllowed"] is False


def test_stage_envelopes_fail_closed_at_known_boundaries() -> None:
    valid_stage1 = {
        "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
        "entities": [
            {
                "candidateId": "e1",
                "type": "Task",
                "startOffset": 0,
                "endOffset": 4,
                "confidence": 1.0,
            }
        ],
        "abstention": {"required": False, "reason": None},
    }
    unknown_field = dict(valid_stage1)
    unknown_field["providerMetadata"] = {}
    with pytest.raises(ContractViolation, match="unbound fields"):
        validate_stage1_response(unknown_field, source_length=10)

    valid_entity = EntityCandidate("e1", "Task", 0, 4, Decimal("1"))
    invalid_stage2 = {
        "schemaVersion": "s12-f-12.stage2.relation-envelope.v2",
        "relations": [
            {
                "predicate": "supports",
                "sourceEntityId": "e1",
                "targetEntityId": "missing",
                "confidence": 1.0,
                "triggerQuote": "supports",
                "evidence": {"startOffset": 0, "endOffset": 4},
            }
        ],
        "abstention": {"required": False, "reason": None},
    }
    with pytest.raises(ContractViolation, match="invalid candidate"):
        validate_stage2_response(
            invalid_stage2, candidate_table=[valid_entity], source_length=10
        )


def test_evidence_materializer_rejects_quote_mismatch_after_exact_relation_match() -> None:
    source = "task supports risk"
    trigger_start = source.index("supports")
    relation_end = len(source)
    gold = [
        {
            "predicate": "supports",
            "sourceEntityId": "g1",
            "targetEntityId": "g2",
            "startOffset": 0,
            "endOffset": relation_end,
            "triggerDigest": "sha256:" + hashlib.sha256(b"supports").hexdigest(),
        }
    ]
    predicted = [
        RelationCandidate(
            "supports",
            "p1",
            "p2",
            Decimal("1"),
            0,
            relation_end,
            "support",  # deliberate mismatch; the exact relation still matches
        )
    ]
    context = materialize_evidence_context(
        source,
        [(trigger_start, trigger_start + len("supports"))],
        sentence=(0, relation_end),
        clause=(0, relation_end),
    )
    result = score_relations(
        gold,
        predicted,
        gold_entities={"g1": (0, 4, "Task"), "g2": (14, 18, "Risk")},
        predicted_entities={"p1": (0, 4, "Task"), "p2": (14, 18, "Risk")},
        evidence_contexts={("supports", "p1", "p2"): context},
    )
    assert result["semantic"]["counts"]["exactMatch"] == 1
    assert result["endpointResolution"]["resolved"] == 2
    assert result["evidence"]["counts"]["unsupported"] == 1
    assert result["evidence"]["supportRate"] == 0.0
