"""Fail-closed RM-68 prerequisite audit and blocked-packet contract gate."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "evaluation/sprint-12/harness/s12-rm68-preregistration-blocked.v1.json"
SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-rm68-preregistration-blocked.schema.v1.json"
STATE = ROOT / "evaluation/sprint-12/current-state.v1.json"
G6 = ROOT / "evaluation/sprint-12/heldout/g6-packet.v1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _errors(packet: dict, schema: dict) -> list:
    Draft202012Validator.check_schema(schema)
    return list(Draft202012Validator(schema).iter_errors(packet))


def test_rm68_blocked_packet_is_schema_valid_and_source_bound() -> None:
    packet = _load(PACKET)
    schema = _load(SCHEMA)
    assert _errors(packet, schema) == []
    for binding in packet["sourceBindings"]:
        assert _digest(ROOT / binding["path"]) == binding["digest"]
    assert packet["status"] == "DRAFT_BLOCKED_EXTERNAL_CUSTODY"
    assert packet["disposition"] == "NOT_A_PREREGISTRATION"
    assert packet["externalCustody"]["status"] == "CUSTODY_NOT_ESTABLISHED"
    assert packet["externalCustody"]["payloadPresent"] is False
    assert packet["externalCustody"]["payloadNonReconstructible"] is False
    assert packet["datasetBinding"]["availableToRepository"] is False
    assert packet["candidateBinding"]["frozen"] is False
    assert packet["issuanceCriteria"]["allCriteriaSatisfied"] is False
    assert all(value is False for value in packet["noExecutionLocks"].values())


def test_rm68_audit_matches_authoritative_missing_prerequisites() -> None:
    state = _load(STATE)
    g6 = _load(G6)
    assert state["status"] == "F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED"
    assert state["nextTasks"] == ["DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY"]
    assert state["currentEvidence"]["rm67HumanCorrectionBurdenContract"]["custodyStatus"] == "CUSTODY_NOT_ESTABLISHED"
    assert state["currentEvidence"]["internalDevelopmentPoc"]["status"] == "F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED"
    assert state["currentEvidence"]["internalDevelopmentPoc"]["reviewerMode"] == "PRIMARY_AGENT_PROXY_OWNER_JUDGMENT"
    assert state["currentEvidence"]["internalDevelopmentPoc"]["supportedFinalizedAssertions"] == 60
    assert state["currentEvidence"]["internalDevelopmentPoc"]["unsupportedFinalizedAssertions"] == 0
    assert state["experimentState"]["candidateFrozen"] is False
    assert state["experimentState"]["candidateSelection"] == "NO_SELECTION"
    assert g6["custody"]["status"] == "CUSTODY_NOT_ESTABLISHED"
    assert g6["custody"]["payloadPresent"] is False
    assert g6["custody"]["failures"]
    assert g6["preregistration"]["candidate"] is None
    assert g6["preregistration"]["heldOutInspected"] is False


def test_rm68_schema_rejects_issuance_extra_field_and_source_mutations() -> None:
    packet = _load(PACKET)
    schema = _load(SCHEMA)
    mutations = (
        lambda value: value.__setitem__("status", "PREREGISTRATION_ISSUED"),
        lambda value: value.__setitem__("unexpectedField", True),
        lambda value: value["externalCustody"].__setitem__("payloadPresent", True),
    )
    for mutate in mutations:
        mutated = copy.deepcopy(packet)
        mutate(mutated)
        assert _errors(mutated, schema), "unsafe RM-68 mutation was schema-valid"


def test_rm68_packet_does_not_claim_issuance_or_execution() -> None:
    packet = _load(PACKET)
    text = (ROOT / "docs/sprint-plans/sprint-12/rm68-preregistration-blocked.v1.md").read_text(encoding="utf-8")
    assert "not an issued preregistration" in text
    assert "No dataset IDs, payloads, candidate IDs" in text
    assert packet["nonClaims"]
    assert packet["nextPermittedAction"] == "NO_RM68_ACTION_UNTIL_OWNER_REOPENS_WITH_EXTERNAL_CUSTODY"
    assert packet["developmentWaiver"] == {
        "status": "DEFERRED_DEV_ONLY",
        "phaseStatus": "DEVELOPMENT_COMPLETE_EXTERNAL_VALIDATION_DEFERRED",
        "rm68IssuanceDeferred": True,
        "externalValidationDeferred": True,
        "reopenRequires": "OWNER_REVIEW_WITH_EXTERNAL_CUSTODY_AND_FROZEN_CANDIDATE",
    }
