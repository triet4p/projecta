from __future__ import annotations

import copy
import json
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v4 as v4  # noqa: E402
import s12_f12_rm38_reconciliation_diagnosis as rm38  # noqa: E402
import s12_f12_rm40_offline_runtime as rm40  # noqa: E402
from sprint12_f12_two_step_contracts_v5 import EntityCandidate, RelationCandidate  # noqa: E402
from sprint12_provider_adapter import ProviderCapture  # noqa: E402


def _case() -> dict[str, object]:
    return rm38._load_first_case()


def _gold_table(case: dict[str, object]) -> list[dict[str, object]]:
    return rm38._gold_table(case)


def _entities() -> tuple[EntityCandidate, ...]:
    return (
        EntityCandidate("entity-01", "Task", 0, 21, Decimal("1")),
        EntityCandidate("entity-02", "Risk", 29, 43, Decimal("1")),
    )


def _capture() -> ProviderCapture:
    return ProviderCapture(
        payload={"schemaVersion": "mock", "relations": []},
        usage={"promptCacheHitTokens": 0, "promptCacheMissTokens": 1, "outputTokens": 1},
        retry_count=0,
    )


def _score(case: dict[str, object], relations: tuple[RelationCandidate, ...]) -> dict[str, object]:
    return v4._arm_record(
        case,
        stage1=None,
        stage1_failure=None,
        predicted_entities=_entities(),
        stage2=_capture(),
        stage2_failure=None,
        relations=relations,
        abstention=False,
        gold_candidates=_gold_table(case),
        is_gold_arm=False,
    )


def _relation(
    predicate: str = "answers",
    *,
    source: str = "entity-01",
    target: str = "entity-02",
    trigger: str | None = "answers",
    evidence: tuple[int, int] | None = (0, 82),
) -> RelationCandidate:
    return RelationCandidate(
        predicate,
        source,
        target,
        Decimal("1"),
        None if evidence is None else evidence[0],
        None if evidence is None else evidence[1],
        trigger,
    )


def test_exact_invalid_relation_counts_once_and_reconciles() -> None:
    case = _case()
    relations = (_relation(trigger=None),)
    result = rm40.diagnose_arm(
        case,
        relations=relations,
        predicted_entities=_entities(),
        gold_candidates=_gold_table(case),
        is_gold_arm=False,
        score_result=_score(case, relations),
    )
    assert result["exactSemanticPairCount"] == 1
    assert result["materializerInvalidEvidenceCount"] == 1
    assert result["evidenceReasonCounts"]["trigger_quote_missing"] == 1
    assert result["reasonCountsReconciled"] is True


def test_non_exact_invalid_relation_does_not_inflate_reasons() -> None:
    case = _case()
    relations = (_relation("supports", trigger=None),)
    result = rm40.diagnose_arm(
        case,
        relations=relations,
        predicted_entities=_entities(),
        gold_candidates=_gold_table(case),
        is_gold_arm=False,
        score_result=_score(case, relations),
    )
    assert result["exactSemanticPairCount"] == 0
    assert result["materializerInvalidEvidenceCount"] == 0
    assert sum(result["evidenceReasonCounts"].values()) == 0


def test_extra_invalid_relation_does_not_inflate_reasons() -> None:
    case = _case()
    relations = (_relation(), _relation("supports", trigger=None))
    result = rm40.diagnose_arm(
        case,
        relations=relations,
        predicted_entities=_entities(),
        gold_candidates=_gold_table(case),
        is_gold_arm=False,
        score_result=_score(case, relations),
    )
    assert result["exactSemanticPairCount"] == 1
    assert result["materializerInvalidEvidenceCount"] == 0
    assert sum(result["evidenceReasonCounts"].values()) == 0


@pytest.mark.parametrize(
    "relation",
    [_relation("supports"), _relation("answers", source="missing")],
)
def test_wrong_or_missing_semantics_have_no_evidence_domain(relation: RelationCandidate) -> None:
    case = _case()
    result = rm40.diagnose_arm(
        case,
        relations=(relation,),
        predicted_entities=_entities(),
        gold_candidates=_gold_table(case),
        is_gold_arm=False,
        score_result=_score(case, (relation,)),
    )
    assert result["exactSemanticPairCount"] == 0
    assert result["materializerInvalidEvidenceCount"] == 0
    assert sum(result["evidenceReasonCounts"].values()) == 0


def test_span_projection_strips_entity_type_before_classifier() -> None:
    projected = rm40.project_entity_spans(_entities(), _gold_table(_case()), is_gold_arm=False)
    assert projected == {"entity-01": (0, 21), "entity-02": (29, 43)}
    assert all(len(span) == 2 for span in projected.values())


def test_malformed_detail_fails_closed_to_registered_reason() -> None:
    reason = rm40.diagnose_evidence_failure(
        SimpleNamespace(trigger_quote="answers", evidence_start="bad", evidence_end=1),
        context=None,
        endpoint_spans=((0, 1), (2, 3)),
    )
    assert reason == rm40.SanitizedReason("materializer_detail_unavailable", False)


def test_mismatch_refusal_is_fail_closed() -> None:
    case = _case()
    relations = (_relation("supports", trigger=None),)
    score = _score(case, relations)
    mismatched = copy.deepcopy(score)
    mismatched["relation"]["evidence"]["counts"]["unsupported"] = 1
    with pytest.raises(rm40.RM40ReconciliationError, match="reconcile"):
        rm40.diagnose_arm(
            case,
            relations=relations,
            predicted_entities=_entities(),
            gold_candidates=_gold_table(case),
            is_gold_arm=False,
            score_result=mismatched,
        )


def test_all_valid_has_zero_reasons_and_raw_data_exclusion() -> None:
    case = _case()
    relations = (_relation(),)
    result = rm40.diagnose_arm(
        case,
        relations=relations,
        predicted_entities=_entities(),
        gold_candidates=_gold_table(case),
        is_gold_arm=False,
        score_result=_score(case, relations),
    )
    assert result["materializerInvalidEvidenceCount"] == 0
    assert sum(result["evidenceReasonCounts"].values()) == 0
    serialized = json.dumps(result)
    assert '"source_text"' not in serialized
    assert '"providerPayload"' not in serialized
    assert result["rawDataIncluded"] is False


def test_prospective_custody_is_144_96_one_persist_no_retry_no_overwrite() -> None:
    custody = rm40.prospective_custody()
    assert custody["providerCalls"] == 0
    assert custody["plannedProviderCalls"] == 144
    assert custody["plannedRelationBranchOutputs"] == 96
    assert custody["retryCount"] == 0
    assert custody["persistCount"] == 1
    assert custody["overwriteRejected"] is True
    with pytest.raises(rm40.RM40ReconciliationError, match="overwrite"):
        rm40.prospective_custody(output_exists_before=True)
