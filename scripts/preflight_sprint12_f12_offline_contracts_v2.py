#!/usr/bin/env -S uv run --script
"""Digest-bound, zero-call preflight for the superseding f12 offline package."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v2.json"
HISTORICAL_PACKAGE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v1.json"
)
FIXTURES = ROOT / "evaluation/sprint-12/harness/s12-f-12-oracle-fixtures.v2.json"
SCORER = ROOT / "scripts/sprint12_f12_two_step_contracts_v2.py"

APPROVED_THRESHOLDS = {
    "entityMacroF1Min": 0.85,
    "entitySpanExactMin": 0.95,
    "entityHallucinationRateMax": 0.05,
    "abstentionPrecisionMin": 0.90,
    "abstentionRecallMin": 0.90,
    "abstentionF1Min": 0.90,
    "relationSemanticMicroF1Min": 0.80,
    "relationSemanticMacroF1Min": 0.80,
    "predicateAccuracyMin": 0.85,
    "endpointDirectionAccuracyMin": 0.90,
    "missingEndpointRateMax": 0.05,
    "reversedEndpointRateMax": 0.05,
    "relationEvidenceSupportMin": 0.85,
    "relationEvidenceExactMin": 0.85,
    "relationHallucinationRateMax": 0.05,
    "hardFailureCount": 0,
    "retryCount": 0,
    "pricingFailureCount": 0,
    "goldRelationsIntegrityScore": 1.0,
    "goldRelationsMaterializerFailures": 0,
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact is not an object: {path}")
    return value


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_bound_digests(package: dict[str, Any]) -> None:
    for relative, expected in package.get("boundDigests", {}).items():
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"bound artifact is missing: {relative}")
        if _digest(path) != expected:
            raise ValueError(f"bound artifact digest mismatch: {relative}")


def _entities(items: list[dict[str, Any]], scorer: Any) -> tuple[Any, ...]:
    return scorer.validate_stage1_candidates(items, source_length=10_000)


def _run_deterministic_fixtures(fixtures: dict[str, Any]) -> dict[str, Any]:
    from sprint12_f12_two_step_contracts_v2 import (
        score_entity_candidates,
        score_relations,
        validate_stage1_response,
        validate_stage2_response,
    )

    arms = fixtures.get("oracleArms")
    if not isinstance(arms, list) or len(arms) != 3:
        raise ValueError("exactly three oracle arms are required")
    ids = {str(arm.get("id")) for arm in arms}
    if ids != {"gold-relations", "predicted-entities", "gold-entities"}:
        raise ValueError("oracle arms are not the approved paired set")
    if fixtures.get("rawSourceTextIncluded") is not False:
        raise ValueError("raw source text is present in fixtures")
    results: dict[str, Any] = {}
    for arm in arms:
        if arm.get("contextDigest") != fixtures.get("pairedContextDigest") or arm.get(
            "configurationDigest"
        ) != fixtures.get("pairedConfigurationDigest"):
            raise ValueError(f"paired digest mismatch: {arm.get('id')}")
        candidates, _ = validate_stage1_response(
            arm["stage1Response"], source_length=arm["sourceLength"]
        )
        table = _entities(
            arm["candidateTable"], sys.modules["sprint12_f12_two_step_contracts_v2"]
        )
        if candidates != table:
            raise ValueError(
                f"stage-1 response does not equal server-owned table: {arm.get('id')}"
            )
        relations, _ = validate_stage2_response(
            arm["stage2Response"],
            candidate_table=table,
            source_length=arm["sourceLength"],
        )
        gold_entity_score = score_entity_candidates(arm["goldEntities"], candidates)
        gold_entities = {
            str(item["id"]): (
                int(item["startOffset"]),
                int(item["endOffset"]),
                str(item["type"]),
            )
            for item in arm["goldEntities"]
        }
        candidate_entities = {
            item.candidate_id: (item.start, item.end, item.entity_type)
            for item in candidates
        }
        relation_score = score_relations(
            arm["goldRelations"],
            relations,
            gold_entities=gold_entities,
            predicted_entities=candidate_entities,
        )
        results[str(arm["id"])] = {
            "entity": gold_entity_score,
            "relation": relation_score,
            "providerCalls": arm["providerCalls"],
        }
    integrity = results["gold-relations"]["relation"]
    if (
        integrity["semantic"]["microF1"] != 1.0
        or integrity["semantic"]["macroF1"] != 1.0
        or integrity["evidence"]["exactRate"] != 1.0
    ):
        raise ValueError("gold-relations integrity fixture did not score 1.0")
    return results


def run_preflight() -> dict[str, Any]:
    package = _load(PACKAGE)
    historical = _load(HISTORICAL_PACKAGE)
    fixtures = _load(FIXTURES)
    _verify_bound_digests(package)
    historical_digest = _digest(HISTORICAL_PACKAGE)
    if package.get("supersedes", {}).get("digest") != historical_digest:
        raise ValueError("historical v1 package is not digest-bound")
    if package.get("approvedThresholds") != APPROVED_THRESHOLDS:
        raise ValueError("approved thresholds are not reconciled")
    if (
        package.get("governance", {}).get("providerExecutionAuthorized") is not False
        or package.get("governance", {}).get("preregistrationAuthorized") is not False
    ):
        raise ValueError("offline package opens execution or preregistration")
    if (
        not historical.get("governance", {}).get("f12ProviderExecutionAuthorized")
        is False
    ):
        raise ValueError("historical package governance is not closed")
    results = _run_deterministic_fixtures(fixtures)
    if list(
        ROOT.glob("evaluation/sprint-12/optimization/s12-f-12-*-authorization*.json")
    ):
        raise ValueError("f12 authorization artifact exists")
    if list(
        ROOT.glob("evaluation/sprint-12/optimization/s12-f-12-*-preregistration*.json")
    ):
        raise ValueError("f12 preregistration artifact exists")
    return {
        "status": "OFFLINE_CONTRACTS_READY_ZERO_CALL_V2",
        "experimentId": "s12-f-12",
        "providerCalls": 0,
        "oracleArms": 3,
        "deterministicFixtureResults": results,
        "providerExecutionAuthorized": False,
        "preregistrationIssued": False,
        "heldOutAccess": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), indent=2, sort_keys=True))
