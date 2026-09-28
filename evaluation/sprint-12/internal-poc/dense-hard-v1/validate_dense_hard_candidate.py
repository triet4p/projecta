"""Source-only validator for the frozen dense-hard candidate.

This validator never opens any gold, evaluator, review, or score artifact. It
checks the candidate against the supplied source payload and the local output
schema, including Unicode-code-point spans and relation endpoint integrity.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - explicit environment failure
    raise SystemExit("jsonschema is required for source-only validation") from exc

HERE = Path(__file__).resolve().parent
PAYLOAD = HERE / "dense-hard-source-payload.v1.json"
SCHEMA = HERE / "dense-hard-candidate.v1.schema.json"
CANDIDATE = HERE / "dense-hard-candidate.v1.json"
SCOPE = "projecta.synthetic.s12.dense-hard"
PREDICATES = {"implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy"}
TYPES = {"Requirement", "Decision", "Question", "Task", "Risk", "Assumption", "Constraint", "ProgressClaim", "ResearchFinding"}
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRETISH = re.compile(r"(?i)(sk-[A-Za-z0-9]{16,}|api[_ -]?key|password|secret|bearer\s+[A-Za-z0-9._-]{12,})")


def canonical_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(candidate), key=lambda e: list(e.path))
    if errors:
        fail("schema: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errors))
    if "dense-hard-gold" in str(CANDIDATE).lower() or "evaluator-manifest" in str(CANDIDATE).lower():
        fail("candidate path is outside the source-only boundary")
    if "gold" in candidate.get("nonClaims", [])[0].lower() and candidate["goldIncluded"]:
        fail("goldIncluded must remain false")
    if candidate["payloadDigest"] != payload["payloadDigest"]:
        fail("candidate does not preserve source payload digest")
    payload_without_digest = dict(payload)
    payload_without_digest.pop("payloadDigest", None)
    if canonical_digest(payload_without_digest) != payload["payloadDigest"]:
        fail("source payload digest does not match source bytes")
    if candidate["codeDigest"] != file_digest(Path(__file__)):
        fail("codeDigest does not match validator bytes")
    candidate_without_digest = dict(candidate)
    candidate_without_digest.pop("candidateDigest")
    if candidate["candidateDigest"] != canonical_digest(candidate_without_digest):
        fail("candidateDigest does not match canonical candidate content")

    source_by_case = {r["caseId"]: r for r in payload["records"]}
    if len(source_by_case) != 24 or len(candidate["records"]) != 24:
        fail("expected exactly 24 unique source/candidate records")
    seen = set()
    for record in candidate["records"]:
        case_id = record["caseId"]
        if case_id in seen or case_id not in source_by_case:
            fail(f"unexpected or duplicate case: {case_id}")
        seen.add(case_id)
        source = source_by_case[case_id]
        if record["sourceDigest"] != source["sourceDigest"] or record["scenarioId"] != source["scenarioId"] or record["language"] != source["language"]:
            fail(f"source identity mismatch for {case_id}")
        if record["sourceVersion"]["canonicalContentDigest"] != record["sourceDigest"] or record["sourceVersion"]["originalContentDigest"] != record["sourceDigest"]:
            fail(f"source-version digest mismatch for {case_id}")
        response = record["response"]
        if record["responseDigest"] != canonical_digest(response):
            fail(f"responseDigest mismatch for {case_id}")
        if response["projectScopeId"] != SCOPE or record["sourceVersion"]["projectScopeId"] != SCOPE:
            fail(f"project scope mismatch for {case_id}")
        entity_ids = set()
        for entity in response["entities"]:
            if entity["entityId"] in entity_ids or entity["type"] not in TYPES:
                fail(f"invalid entity identity/type for {case_id}")
            entity_ids.add(entity["entityId"])
            evidence = entity["evidence"]
            if evidence["endOffset"] <= evidence["startOffset"] or source["rawText"][evidence["startOffset"]:evidence["endOffset"]] != evidence["text"] or evidence["text"] != entity["label"]:
                fail(f"entity anchor mismatch for {case_id}: {entity['entityId']}")
        relation_ids = set()
        for relation in response["relations"]:
            if relation["relationId"] in relation_ids or relation["predicate"] not in PREDICATES:
                fail(f"invalid relation identity/predicate for {case_id}")
            relation_ids.add(relation["relationId"])
            if relation["sourceEntityId"] not in entity_ids or relation["targetEntityId"] not in entity_ids:
                fail(f"relation endpoint is not a declared entity for {case_id}")
            evidence = relation["evidence"]
            if evidence["endOffset"] <= evidence["startOffset"] or source["rawText"][evidence["startOffset"]:evidence["endOffset"]] != evidence["text"]:
                fail(f"relation anchor mismatch for {case_id}: {relation['relationId']}")
        abstention = response["abstention"]
        if abstention["status"] == "none" and (abstention["abstentionReason"] is not None or abstention["withheldAssertions"]):
            fail(f"none abstention has details for {case_id}")
        if abstention["status"] != "none" and not abstention["abstentionReason"]:
            fail(f"explicit abstention is missing a reason for {case_id}")
        if abstention["status"] == "full" and response["relations"]:
            fail(f"full abstention contains a relation for {case_id}")

    # The synthetic source is non-production. Still reject accidental secret-like
    # payloads in candidate strings without printing their contents.
    serialized = json.dumps(candidate, ensure_ascii=False)
    if SECRETISH.search(serialized):
        fail("secret-like material detected")
    if seen != set(source_by_case):
        fail("candidate does not cover every source case")
    print(json.dumps({"status": "PASS", "records": len(seen), "payloadDigest": candidate["payloadDigest"], "candidateDigest": candidate["candidateDigest"], "codeDigest": candidate["codeDigest"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
