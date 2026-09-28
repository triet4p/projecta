"""Closed-world contract gate for S12-RM-67 (no human study execution)."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "evaluation/sprint-12/harness/s12-rm67-human-correction-burden-contract.v1.json"
SCHEMA_PATH = ROOT / "evaluation/sprint-12/harness/s12-rm67-human-correction-burden-contract.schema.v1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_closed_world(contract: dict, schema: dict) -> None:
    required = set(schema["required"])
    assert set(contract) == required
    assert schema["additionalProperties"] is False
    assert contract["artifactVersion"] == "s12.rm67.human-correction-burden-contract.v1"
    assert contract["contractVersion"] == "human-correction-burden.v1"
    assert contract["status"] == "OWNER_DELEGATED_ACCEPTED_FOR_RM68_PREREGISTRATION_ONLY"
    decision = contract["decision"]
    assert decision == {
        "decisionId": "s12-rm67-threshold-decision-v1",
        "disposition": "ACCEPTED_FOR_RM68_PREREGISTRATION_ONLY",
        "authority": "owner-delegated-contract-review",
        "ownerDelegationRecorded": True,
        "observedHumanResults": False,
        "humanExecutionAuthorized": False,
        "providerCallsAuthorized": False,
        "heldOutInspection": False,
        "custodyStatus": "CUSTODY_NOT_ESTABLISHED",
        "nextPermittedAction": "S12-RM-68_PREREGISTER_HUMAN_FIRST_EVALUATION",
    }
    assert any(
        binding["path"] == "docs/sprint-plans/sprint-12/human-first-extraction-framework.v2.md"
        and binding["role"].startswith("accepted human-first design")
        for binding in contract["sourceBindings"]
    )
    assert any(
        binding["path"] == "docs/sprint-plans/sprint-12/human-first-extraction-framework.v1.md"
        and "immutable proposal/source" in binding["role"]
        for binding in contract["sourceBindings"]
    )
    for binding in contract["sourceBindings"]:
        assert _digest(ROOT / binding["path"]) == binding["digest"]
    thresholds = contract["thresholds"]
    assert thresholds["acceptedWithoutSemanticCorrection"]["minimum"] == 0.7
    assert thresholds["acceptedUnchangedOrMinor"]["minimum"] == 0.85
    assert thresholds["medianReviewTimeReductionVsCounterbalancedManualBaseline"]["minimum"] == 0.3
    assert thresholds["medianReviewTimeSeconds"]["maximum"] == 45
    assert thresholds["p90ReviewTimeSeconds"]["maximum"] == 90
    assert thresholds["meanSemanticEditsPerReviewedItem"]["maximum"] == 2
    assert thresholds["unsupportedFinalizedAssertions"]["maximum"] == 0
    assert thresholds["reviewerAgreementWhenApplicable"]["minimum"] == 0.8
    taxonomy = contract["correctionTaxonomy"]
    assert taxonomy["classes"] == ["unchanged", "minor", "major"]
    assert taxonomy["dimensions"] == ["span", "type", "label", "predicate", "endpoint", "evidence"]
    assert taxonomy["precedence"][0] == {
        "class": "major",
        "whenAnyDimension": ["type", "predicate", "endpoint", "evidence"],
    }
    assert taxonomy["precedence"][1] == {"class": "minor", "whenAnyDimension": ["span", "label"]}
    assert taxonomy["precedence"][2] == {
        "class": "unchanged",
        "when": "no_semantic_or_evidence_dimensions",
    }
    assert taxonomy["legacyMapping"]["formatting-only"] == "unchanged"
    assert set(contract["denominators"]) == {
        "eligibleReviewedItems",
        "acceptanceRates",
        "reviewTime",
        "editBurden",
        "agreement",
        "unsupportedFinalizedAssertions",
        "invalidRecords",
    }
    study = contract["studyDesign"]
    assert study["minimumQualifiedReviewers"] == 3
    assert study["minimumScenarios"] == 12
    assert study["minimumReviewerRecords"] == 36
    assert study["targetRoles"] == ["BrSE", "project-manager", "semantic-reviewer"]
    assert study["counterbalancedSameReviewerManualBaseline"] is True
    assert study["languageMinimumScenarios"] == {"vi": 2, "en": 2, "ja": 2, "mixed": 2}
    assert len(study["requiredJourneys"]) == 8
    assert study["minimumAmbiguityCases"] == 2
    assert study["minimumThreatOrIsolationCases"] == 2
    assert contract["statisticalReporting"]["source"] == "evaluation/sprint-12/metrics.v1.md"
    assert any("F1" in item and "diagnostic" in item for item in contract["nonGoals"])


def _schema_errors(contract: dict, schema: dict) -> list:
    Draft202012Validator.check_schema(schema)
    return list(Draft202012Validator(schema).iter_errors(contract))


def test_rm67_contract_is_valid_and_source_bound() -> None:
    contract = _load(CONTRACT_PATH)
    schema = _load(SCHEMA_PATH)
    assert _schema_errors(contract, schema) == []
    _validate_closed_world(contract, schema)


def test_rm67_schema_rejects_threshold_taxonomy_and_extra_field_mutations() -> None:
    contract = _load(CONTRACT_PATH)
    schema = _load(SCHEMA_PATH)
    for mutate in (
        lambda value: value["thresholds"]["acceptedWithoutSemanticCorrection"].__setitem__("minimum", 0.69),
        lambda value: value["correctionTaxonomy"]["dimensions"].append("free_text"),
        lambda value: value.__setitem__("unexpectedField", True),
    ):
        mutated = copy.deepcopy(contract)
        mutate(mutated)
        assert _schema_errors(mutated, schema), "contract mutation was accepted by schema"


def test_rm67_schema_is_strict_for_core_objects() -> None:
    schema = _load(SCHEMA_PATH)
    assert schema["additionalProperties"] is False
    for name in (
        "thresholds",
        "correctionTaxonomy",
        "denominators",
        "timingPolicy",
        "missingAndDisagreementPolicy",
        "studyDesign",
        "statisticalReporting",
    ):
        assert schema["$defs"][name]["additionalProperties"] is False
    assert schema["$defs"]["threshold"]["additionalProperties"] is False
    assert schema["$defs"]["correctionTaxonomy"]["properties"]["legacyMapping"]["additionalProperties"] is False
