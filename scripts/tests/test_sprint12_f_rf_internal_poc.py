"""Strict internal F-RF PoC selection and truthful agent-proxy review gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc.v1.json"
POC_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc.schema.v1.json"
REVIEW = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v1.json"
REVIEW_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.schema.v1.json"
CANDIDATE_V2 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v2.json"
REVIEW_V2 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v2.json"
CANDIDATE_V2_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v2.schema.json"
REVIEW_V2_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v2.schema.json"
PAYLOAD_V3 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v3.json"
PAYLOAD_V3_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v3.schema.json"
CANDIDATE_V3 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v3.json"
CANDIDATE_V3_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v3.schema.json"
REVIEW_V3 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v3.json"
REVIEW_V3_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v3.schema.json"
PAYLOAD_V4 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v4.json"
PAYLOAD_V4_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v4.schema.json"
CANDIDATE_V4 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v4.json"
CANDIDATE_V4_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v4.schema.json"
REVIEW_V4 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v4.json"
REVIEW_V4_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v4.schema.json"
PAYLOAD_V5 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v5.json"
PAYLOAD_V5_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v5.schema.json"
CANDIDATE_V5 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v5.json"
CANDIDATE_V5_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v5.schema.json"
REVIEW_V5 = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v5.json"
REVIEW_V5_SCHEMA = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v5.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _validate(value: dict, schema: dict) -> None:
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(value))
    assert errors == [], errors


def test_internal_poc_is_strict_source_bound_and_non_external() -> None:
    packet = _load(POC)
    _validate(packet, _load(POC_SCHEMA))
    for binding in packet["sourceBindings"]:
        assert _digest(ROOT / binding["path"]) == binding["digest"]
    dataset = packet["datasetBinding"]
    assert dataset["scenarioCount"] == 12
    assert len(set(dataset["scenarioIds"])) == 12
    assert set(dataset["languages"]) == {"vi", "en", "ja", "mixed"}
    assert packet["reviewerMode"] == "AGENT_PROXY_NOT_HUMAN"
    assert packet["candidateExecution"]["providerCalls"] == 0
    assert packet["candidateExecution"]["runtimeConfigurationPresent"] is False
    assert all("rawText" not in json.dumps(binding) for binding in packet["sourceBindings"])


def test_agent_proxy_review_preserves_missing_outputs_and_fails_gate() -> None:
    packet = _load(REVIEW)
    _validate(packet, _load(REVIEW_SCHEMA))
    assert packet["protocolDigest"] == _digest(POC)
    assert len(packet["records"]) == 12
    assert {record["candidateOutputStatus"] for record in packet["records"]} == {
        "missing-output"
    }
    assert all(record["eligibleForAcceptance"] is False for record in packet["records"])
    assert packet["metrics"]["gateStatus"] == "FAIL_MISSING_OUTPUT_NO_HUMAN_BASELINE"
    assert packet["reviewerMode"] == "AGENT_PROXY_NOT_HUMAN"
    assert packet["humanEvidence"] is False
    assert packet["providerCalls"] == 0


def test_internal_poc_schema_rejects_external_or_success_mutations() -> None:
    packet = _load(POC)
    schema = _load(POC_SCHEMA)
    for field, value in (
        ("status", "ACCEPTED_EXTERNAL_HUMAN_STUDY"),
        ("reviewerMode", "HUMAN_REVIEWER"),
    ):
        mutated = json.loads(json.dumps(packet))
        mutated[field] = value
        assert list(Draft202012Validator(schema).iter_errors(mutated))


def test_deterministic_candidate_and_proxy_review_v2_are_bound_and_fail_closed() -> None:
    candidate = _load(CANDIDATE_V2)
    review = _load(REVIEW_V2)
    _validate(candidate, _load(CANDIDATE_V2_SCHEMA))
    _validate(review, _load(REVIEW_V2_SCHEMA))
    assert candidate["providerCalls"] == 0
    assert candidate["caseCount"] == 12
    assert {case["status"] for case in candidate["caseResults"]} == {"abstained"}
    assert review["candidateDigest"] == _digest(CANDIDATE_V2)
    assert review["metrics"]["gateStatus"] == "FAIL_NO_HUMAN_BASELINE_OR_AGREEMENT"
    assert review["manualBaseline"]["pairedRecords"] == 0
    assert all(record["candidateOutputStatus"] == "abstained" for record in review["records"])
    assert "rawText" not in json.dumps(candidate)
    assert "rawText" not in json.dumps(review)


def test_v3_payload_is_blinded_and_candidate_is_frozen_before_review() -> None:
    payload = _load(PAYLOAD_V3)
    candidate = _load(CANDIDATE_V3)
    _validate(payload, _load(PAYLOAD_V3_SCHEMA))
    _validate(candidate, _load(CANDIDATE_V3_SCHEMA))
    payload_without_digest = dict(payload)
    payload_digest = payload_without_digest.pop("payloadDigest")
    assert payload_digest == _canonical_digest(payload_without_digest)
    assert payload["goldIncluded"] is False
    assert payload["priorScoresIncluded"] is False
    assert payload["priorReviewsIncluded"] is False
    assert all("gold" not in record for record in payload["records"])
    assert candidate["candidateModel"] == "gpt-5.6-luna"
    assert candidate["reasoning"] == "high"
    assert candidate["agentCandidateCalls"] == 12
    assert candidate["providerCalls"] == 0
    assert candidate["reviewOrScoringPerformed"] is False
    candidate_without_digest = dict(candidate)
    candidate_digest = candidate_without_digest.pop("candidateDigest")
    assert candidate_digest == _canonical_digest(candidate_without_digest)
    assert "score" not in json.dumps(candidate)
    assert "priorReviews" not in candidate
    assert "reviewer" not in json.dumps(candidate).lower()


def test_v3_owner_proxy_review_is_exactly_failed_and_bound_to_frozen_candidate() -> None:
    review = _load(REVIEW_V3)
    _validate(review, _load(REVIEW_V3_SCHEMA))
    assert review["candidateDigest"] == "sha256:fbe412d85bc06d6aa6edf1a68ab26146123dd2fa35308e31abf9542e39f2afaa"
    assert [record["correctionClass"] for record in review["records"]] == [
        "unchanged", "major", "unchanged", "major", "unchanged", "major",
        "unchanged", "major", "unchanged", "major", "unchanged", "major",
    ]
    assert [record["semanticEditCount"] for record in review["records"]] == [0, 5, 0, 3, 0, 5, 0, 3, 0, 5, 0, 3]
    assert review["metrics"]["acceptedWithoutSemanticCorrection"]["rate"] == 0.5
    assert review["metrics"]["meanSemanticEditsPerReviewedItem"] == 2.0
    assert review["metrics"]["gateStatus"] == "FAIL_ACCEPTANCE_RATE"
    assert review["humanEvidence"] is False
    assert review["providerCalls"] == 0


def test_v4_payload_is_new_blinded_source_only_and_candidate_has_no_review() -> None:
    payload = _load(PAYLOAD_V4)
    candidate = _load(CANDIDATE_V4)
    _validate(payload, _load(PAYLOAD_V4_SCHEMA))
    _validate(candidate, _load(CANDIDATE_V4_SCHEMA))
    payload_without_digest = dict(payload)
    digest = payload_without_digest.pop("payloadDigest")
    assert digest == _canonical_digest(payload_without_digest)
    assert payload["goldIncluded"] is False
    assert payload["priorScoresIncluded"] is False
    assert payload["priorReviewsIncluded"] is False
    v3_ids = {record["caseId"] for record in _load(PAYLOAD_V3)["records"]}
    v4_ids = {record["caseId"] for record in payload["records"]}
    assert len(v4_ids) == 12 and not v3_ids.intersection(v4_ids)
    assert all("gold" not in record and "score" not in record for record in payload["records"])
    assert all(
        record["sourceDigest"] == "sha256:" + hashlib.sha256(record["rawText"].encode("utf-8")).hexdigest()
        for record in payload["records"]
    )
    assert candidate["candidateModel"] == "gpt-5.6-luna"
    assert candidate["reasoning"] == "high"
    assert candidate["agentCandidateCalls"] == 12
    assert candidate["providerCalls"] == 0
    assert candidate["reviewOrScoringPerformed"] is False
    candidate_without_digest = dict(candidate)
    candidate_digest = candidate_without_digest.pop("candidateDigest")
    assert candidate_digest == _canonical_digest(candidate_without_digest)
    assert all(record["response"]["entities"] for record in candidate["records"])
    assert any(record["response"]["relations"] for record in candidate["records"])
    assert all(record["responseDigest"] == _canonical_digest(record["response"]) for record in candidate["records"])
    repeated = next(record for record in candidate["records"] if record["caseId"] == "s12-a-4103")
    assert len(repeated["response"]["entities"]) == 2
    assert repeated["response"]["entities"][0]["evidence"]["startOffset"] < repeated["response"]["entities"][1]["evidence"]["startOffset"]
    assert "reviewer" not in json.dumps(candidate).lower()
    assert "score" not in json.dumps(candidate["records"]).lower()


def test_v4_owner_proxy_review_preserves_digest_and_edit_burden_failure() -> None:
    review = _load(REVIEW_V4)
    _validate(review, _load(REVIEW_V4_SCHEMA))
    assert review["candidateDigest"] == "sha256:1f33496ac57a1acf3fb21e7e2e6d3da039b582026858a3e238e7af849c9d1ca6"
    assert review["metrics"]["acceptedWithoutSemanticCorrection"] == {"numerator": 2, "rate": 0.1666667, "threshold": 0.7}
    assert review["metrics"]["totalSemanticEdits"] == 28
    assert review["metrics"]["meanSemanticEditsPerReviewedItem"] == 2.333333
    assert review["metrics"]["gateStatus"] == "FAIL_ACCEPTANCE_AND_EDIT_BURDEN"
    assert review["humanEvidence"] is False and review["providerCalls"] == 0


def test_v5_payload_is_new_and_candidate_has_two_mixed_sentence_relations() -> None:
    payload = _load(PAYLOAD_V5)
    candidate = _load(CANDIDATE_V5)
    _validate(payload, _load(PAYLOAD_V5_SCHEMA))
    _validate(candidate, _load(CANDIDATE_V5_SCHEMA))
    payload_without_digest = dict(payload)
    payload_digest = payload_without_digest.pop("payloadDigest")
    assert payload_digest == _canonical_digest(payload_without_digest)
    used = {record["caseId"] for record in _load(PAYLOAD_V3)["records"]}
    used |= {record["caseId"] for record in _load(PAYLOAD_V4)["records"]}
    assert len({record["caseId"] for record in payload["records"]}) == 12
    assert not used.intersection({record["caseId"] for record in payload["records"]})
    assert candidate["candidateModel"] == "gpt-5.6-luna" and candidate["reasoning"] == "high"
    assert candidate["agentCandidateCalls"] == 12 and candidate["providerCalls"] == 0
    assert candidate["reviewOrScoringPerformed"] is False
    assert candidate["candidateDigest"] == _canonical_digest({k: v for k, v in candidate.items() if k != "candidateDigest"})
    assert all(len(record["response"]["relations"]) == 2 for record in candidate["records"])
    for record in candidate["records"]:
        spans = [entity["evidence"] for entity in record["response"]["entities"]]
        assert all(not (a["startOffset"] <= b["startOffset"] and a["endOffset"] >= b["endOffset"] and (a["startOffset"], a["endOffset"]) != (b["startOffset"], b["endOffset"])) for a in spans for b in spans)
    assert "reviewer" not in json.dumps(candidate).lower()


def test_v5_owner_proxy_review_accepts_only_edit_burden_scope() -> None:
    review = _load(REVIEW_V5)
    _validate(review, _load(REVIEW_V5_SCHEMA))
    assert review["candidateDigest"] == "sha256:09679f2cccae8eaf6477e5b1c3dc3baaf0767441f6bbc0a67b3b103b3d1affa1"
    assert review["payloadDigest"] == "sha256:461c22c4adb8b493389c18278925408b4f9b41b3f02035d48f7d8d30e1182ef4"
    assert review["metrics"]["supportedFinalizedAssertions"] == {"numerator": 60, "denominator": 60, "status": "SUPPORTED_SOURCE_BOUND"}
    assert review["metrics"]["unsupportedFinalizedAssertions"] == {"numerator": 0, "denominator": 60, "status": "ZERO_UNSUPPORTED"}
    assert review["metrics"]["acceptedWithoutSemanticCorrection"]["rate"] == 1.0
    assert review["metrics"]["acceptedUnchangedOrMinor"]["rate"] == 1.0
    assert review["metrics"]["gateStatus"] == "EDIT_BURDEN_ONLY_ACCEPTED_AGENT_PROXY"
    assert review["metrics"]["timingStatus"] == "UNMEASURED"
    assert review["metrics"]["reviewerAgreement"]["status"] == "NOT_CLAIMED"
    assert review["humanEvidence"] is False and review["providerCalls"] == 0
