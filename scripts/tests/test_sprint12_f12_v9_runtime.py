from __future__ import annotations

import copy
import json
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v4 as v4  # noqa: E402
import s12_f12_rm38_reconciliation_diagnosis as rm38  # noqa: E402
import s12_f12_rm40_offline_runtime as rm40  # noqa: E402
import run_sprint12_f12_stage_a_v9 as v9  # noqa: E402
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


def _arm(case: dict[str, object], relations: tuple[RelationCandidate, ...]) -> dict[str, object]:
    v9._PENDING_SCHEMA_REASONS.clear()
    v9._configure()
    return v9._arm_record_v9(
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


def test_v9_schemas_are_closed_and_versioned() -> None:
    report_schema = json.loads(
        (ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v9.json").read_text()
    )
    authorization_schema = json.loads(
        (ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v9.json").read_text()
    )
    Draft202012Validator.check_schema(report_schema)
    Draft202012Validator.check_schema(authorization_schema)
    assert report_schema["$id"] == "s12-f-12.stage-a-report.v9"
    assert authorization_schema["$id"] == "s12-f-12.authorization.v9"
    assert report_schema["additionalProperties"] is False
    assert authorization_schema["additionalProperties"] is False


def test_v9_integrates_rm40_exact_invalid_and_all_valid_paths() -> None:
    case = _case()
    invalid = _arm(case, (_relation(trigger=None),))
    assert invalid["relation"]["invalidEvidenceCount"] == 1
    assert invalid["diagnostics"]["evidenceReasonCounts"]["trigger_quote_missing"] == 1
    valid = _arm(case, (_relation(),))
    assert valid["relation"]["invalidEvidenceCount"] == 0
    assert sum(valid["diagnostics"]["evidenceReasonCounts"].values()) == 0


def test_v9_excludes_non_exact_extra_wrong_and_missing_from_evidence_domain() -> None:
    case = _case()
    for relation in (
        _relation("supports", trigger=None),
        _relation(source="missing", trigger=None),
    ):
        result = _arm(case, (relation,))
        assert result["relation"]["invalidEvidenceCount"] == 0
        assert sum(result["diagnostics"]["evidenceReasonCounts"].values()) == 0
    result = _arm(case, (_relation(), _relation("supports", trigger=None)))
    assert result["relation"]["invalidEvidenceCount"] == 0
    assert sum(result["diagnostics"]["evidenceReasonCounts"].values()) == 0


def test_v9_duplicate_order_tie_and_mixed_pairing_matches_rm40() -> None:
    case = _case()
    gold = _gold_table(case)
    entities = _entities()
    duplicate_case = copy.deepcopy(case)
    duplicate_case["gold"]["relations"] = [
        copy.deepcopy(case["gold"]["relations"][0]),
        copy.deepcopy(case["gold"]["relations"][0]),
    ]
    duplicate = (_relation(), _relation())
    assert rm40.exact_semantic_pairs(
        duplicate_case, duplicate, entities, gold, is_gold_arm=False
    ) == ((0, 0), (1, 1))
    assert rm40.exact_semantic_pairs(
        duplicate_case, tuple(reversed(duplicate)), entities, gold, is_gold_arm=False
    ) == ((0, 0), (1, 1))

    mixed = _arm(case, (_relation(trigger=None), _relation("supports", trigger=None)))
    assert mixed["relation"]["semantic"]["counts"]["exactMatch"] == 1
    assert mixed["relation"]["invalidEvidenceCount"] == 1
    assert sum(mixed["diagnostics"]["evidenceReasonCounts"].values()) == 1


def test_v9_mismatch_malformed_and_raw_data_fail_closed() -> None:
    case = _case()
    relation = _relation("supports", trigger=None)
    score = v4._arm_record(
        case,
        stage1=None,
        stage1_failure=None,
        predicted_entities=_entities(),
        stage2=_capture(),
        stage2_failure=None,
        relations=(relation,),
        abstention=False,
        gold_candidates=_gold_table(case),
        is_gold_arm=False,
    )
    mismatch = copy.deepcopy(score)
    mismatch["relation"]["evidence"]["counts"]["unsupported"] = 1
    with pytest.raises(rm40.RM40ReconciliationError):
        rm40.diagnose_arm(
            case,
            relations=(relation,),
            predicted_entities=_entities(),
            gold_candidates=_gold_table(case),
            is_gold_arm=False,
            score_result=mismatch,
        )
    reason = rm40.diagnose_evidence_failure(
        SimpleNamespace(trigger_quote="answers", evidence_start="bad", evidence_end=1),
        context=None,
        endpoint_spans=((0, 1), (2, 3)),
    )
    assert reason == rm40.SanitizedReason("materializer_detail_unavailable", False)
    output = _arm(case, (_relation(trigger=None),))
    serialized = json.dumps(output)
    assert "source_text" not in serialized
    assert "providerPayload" not in serialized


class _SpyAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def capture_stage(self, **_: object) -> ProviderCapture:
        self.calls += 1
        return _capture()


def test_v9_unauthorized_path_makes_zero_provider_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _SpyAdapter()
    monkeypatch.setattr(v9, "validate_preparation_v9", lambda *args, **kwargs: {})
    with pytest.raises(Exception, match="authorization"):
        v9.run_stage_a(provider_adapter=spy, authorization_path=None)
    assert spy.calls == 0


def test_v9_prospective_custody_is_144_96_once_no_retry_no_overwrite() -> None:
    custody = rm40.prospective_custody()
    assert custody["providerCalls"] == 0
    assert custody["plannedProviderCalls"] == 144
    assert custody["plannedRelationBranchOutputs"] == 96
    assert custody["persistCount"] == 1
    assert custody["retryCount"] == 0
    with pytest.raises(rm40.RM40ReconciliationError):
        rm40.prospective_custody(output_exists_before=True)
