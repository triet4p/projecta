#!/usr/bin/env -S uv run --script
"""Closed-set, digest-bound zero-call preflight for RM-20D."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v5.json"
FIXTURES = ROOT / "evaluation/sprint-12/harness/s12-f-12-oracle-fixtures.v5.json"
SCHEMA1 = (
    ROOT
    / "evaluation/sprint-12/harness/s12-f-12-stage-1-entity-envelope.schema.v2.json"
)
SCHEMA2 = (
    ROOT
    / "evaluation/sprint-12/harness/s12-f-12-stage-2-relation-envelope.schema.v2.json"
)

REQUIRED_BOUND_PATHS = frozenset(
    {
        "evaluation/sprint-12/optimization/s12-f-12-two-step-extraction-design-proposal.v1.json",
        "evaluation/sprint-12/optimization/s12-f-12-two-step-extraction-design-review.v1.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts-review.v2.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts-review.v3.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts-review.v4.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v1.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v2.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v3.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v4.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-1-entity-envelope.schema.v2.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-2-relation-envelope.schema.v2.json",
        "evaluation/sprint-12/harness/relation-trigger-contract.v1.json",
        "evaluation/sprint-12/harness/s12-f-12-oracle-fixtures.v5.json",
        "scripts/sprint12_f12_two_step_contracts_v5.py",
        "scripts/preflight_sprint12_f12_offline_contracts_v5.py",
    }
)

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
    bindings = package.get("boundDigests")
    if not isinstance(bindings, dict) or set(bindings) != REQUIRED_BOUND_PATHS:
        raise ValueError("required digest binding set is missing or not exact")
    for relative, expected in bindings.items():
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"bound artifact is missing: {relative}")
        if _digest(path) != expected:
            raise ValueError(f"bound artifact digest mismatch: {relative}")


def _synthetic_source() -> str:
    return "A" * 10 + "supports" + "B" * 12 + "supports" + "C" * 10 + "D" * 32


def _contexts(
    raw: Mapping[str, Any], *, source_text: str
) -> dict[tuple[str, str, str], Any]:
    from sprint12_f12_two_step_contracts_v5 import EvidenceContext, TriggerOccurrence

    result = {}
    for key, value in raw.items():
        predicate, source_id, target_id = key.split("|", 2)
        result[(predicate, source_id, target_id)] = EvidenceContext(
            len(source_text),
            str(value["sourceDigest"]),
            source_text,
            tuple(
                TriggerOccurrence(
                    int(item["startOffset"]),
                    int(item["endOffset"]),
                    str(item["quoteDigest"]),
                )
                for item in value["triggerOccurrences"]
            ),
            tuple(value["sentence"]),
            tuple(value["clause"]),
        )
    return result


def _run_deterministic_fixtures(fixtures: dict[str, Any]) -> dict[str, Any]:
    from sprint12_f12_two_step_contracts_v5 import (
        score_entity_candidates,
        score_relations,
        validate_stage1_response,
        validate_stage2_response,
    )

    source_text = _synthetic_source()
    if (
        fixtures.get("sourceLength") != len(source_text)
        or fixtures.get("sourceDigest")
        != "sha256:" + hashlib.sha256(source_text.encode()).hexdigest()
    ):
        raise ValueError("synthetic source proof does not match fixture digest")
    arms = fixtures.get("oracleArms")
    if not isinstance(arms, list) or {arm.get("id") for arm in arms} != {
        "gold-relations",
        "predicted-entities",
        "gold-entities",
    }:
        raise ValueError("exactly the approved three oracle arms are required")
    if fixtures.get("rawSourceTextIncluded") is not False:
        raise ValueError("raw source text is present in fixtures")
    results: dict[str, Any] = {}
    for arm in arms:
        if arm.get("contextDigest") != fixtures.get("pairedContextDigest") or arm.get(
            "configurationDigest"
        ) != fixtures.get("pairedConfigurationDigest"):
            raise ValueError(f"paired digest mismatch: {arm.get('id')}")
        candidates, _ = validate_stage1_response(
            arm["stage1Response"], source_length=len(source_text)
        )
        table, _ = validate_stage1_response(
            {
                "schemaVersion": arm["stage1Response"]["schemaVersion"],
                "entities": arm["candidateTable"],
                "abstention": {"required": False, "reason": None},
            },
            source_length=len(source_text),
        )
        if candidates != table:
            raise ValueError(
                f"stage-1 response does not equal server-owned table: {arm.get('id')}"
            )
        relations, _ = validate_stage2_response(
            arm["stage2Response"], candidate_table=table, source_length=len(source_text)
        )
        gold_entities = {
            str(item["id"]): (
                int(item["startOffset"]),
                int(item["endOffset"]),
                str(item["type"]),
            )
            for item in arm["goldEntities"]
        }
        predicted_entities = {
            item.candidate_id: (item.start, item.end, item.entity_type)
            for item in candidates
        }
        relation_score = score_relations(
            arm["goldRelations"],
            relations,
            gold_entities=gold_entities,
            predicted_entities=predicted_entities,
            evidence_contexts=_contexts(
                arm["evidenceContexts"], source_text=source_text
            ),
        )
        results[str(arm["id"])] = {
            "entity": score_entity_candidates(arm["goldEntities"], candidates),
            "relation": relation_score,
            "providerCalls": arm["providerCalls"],
        }
    integrity = results["gold-relations"]["relation"]
    renamed = results["predicted-entities"]["relation"]
    if (
        integrity["semantic"]["microF1"] != 1.0
        or integrity["semantic"]["macroF1"] != 1.0
        or integrity["endpointResolution"]["resolved"] != 4
        or integrity["endpointResolution"]["wrong"] != 0
        or integrity["evidence"]["exactRate"] != 1.0
    ):
        raise ValueError("gold-relations reuse fixture did not score 1.0")
    if (
        renamed["semantic"]["truePositive"] != 2
        or renamed["endpointResolution"]["resolved"] != 4
        or renamed["endpointResolution"]["missing"] != 0
    ):
        raise ValueError("local-ID reuse fixture did not resolve repeated endpoints")
    return results


def run_preflight() -> dict[str, Any]:
    package = _load(PACKAGE)
    fixtures = _load(FIXTURES)
    historical_v4 = _load(
        ROOT / "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v4.json"
    )
    schema1 = _load(SCHEMA1)
    schema2 = _load(SCHEMA2)
    _verify_bound_digests(package)
    if package.get("supersedes", {}).get("digest") != _digest(
        ROOT / "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v4.json"
    ):
        raise ValueError("historical v4 package is not digest-bound")
    if (
        historical_v4.get("governance", {}).get("providerExecutionAuthorized")
        is not False
    ):
        raise ValueError("historical v4 governance is not closed")
    if package.get("approvedThresholds") != APPROVED_THRESHOLDS:
        raise ValueError("approved thresholds are not reconciled")
    if (
        schema1.get("additionalProperties") is not False
        or schema2.get("additionalProperties") is not False
    ):
        raise ValueError("bound schemas permit unbound fields")
    if (
        package.get("governance", {}).get("providerExecutionAuthorized") is not False
        or package.get("governance", {}).get("preregistrationAuthorized") is not False
    ):
        raise ValueError("offline package opens execution or preregistration")
    if list(
        ROOT.glob("evaluation/sprint-12/optimization/s12-f-12-*-authorization*.json")
    ) or list(
        ROOT.glob("evaluation/sprint-12/optimization/s12-f-12-*-preregistration*.json")
    ):
        raise ValueError("f12 authorization or preregistration artifact exists")
    results = _run_deterministic_fixtures(fixtures)
    return {
        "status": "OFFLINE_CONTRACTS_READY_ZERO_CALL_V5",
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
