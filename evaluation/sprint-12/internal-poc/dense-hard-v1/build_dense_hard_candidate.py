"""Build the frozen Sprint 12 dense-hard candidate from source only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PAYLOAD_PATH = HERE / "dense-hard-source-payload.v1.json"
OUT_PATH = HERE / "dense-hard-candidate.v1.json"
SCOPE = "projecta.synthetic.s12.dense-hard"


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def span(text: str, quote: str, occurrence: int = 0) -> dict:
    start = -1
    for _ in range(occurrence + 1):
        start = text.find(quote, start + 1)
    if start < 0:
        raise ValueError(f"quote not found: {quote!r}")
    return {"startOffset": start, "endOffset": start + len(quote), "text": quote}


# Each entity tuple is (label, type, occurrence). Relation tuples are
# (predicate, source entity number, target entity number, exact evidence quote).
CASES = {
    "001": ([
        ("Release train", "Task", 0), ("API contract", "Requirement", 0),
        ("schema registry", "Task", 0), ("unsafe migration", "Risk", 0)],
        [("dependsOn", 0, 1, "Release train depends on API contract"), ("implements", 1, 2, "API contract implements schema registry"), ("blocks", 2, 3, "Schema registry blocks unsafe migration")], None),
    "002": ([
        ("Ops runbook", "Requirement", 0), ("Incident bridge", "Task", 0),
        ("Escalation question", "Question", 0), ("on-call roster", "Constraint", 0)],
        [("supports", 0, 1, "Ops runbook supports incident bridge"), ("answers", 1, 2, "Incident bridge answers escalation question"), ("dependsOn", 2, 3, "Escalation question dependsOn on-call roster")], None),
    "003": ([
        ("Quy trình thanh toán", "Task", 0), ("cổng đối soát", "Task", 0),
        ("Ledger nội bộ", "Task", 0), ("dữ liệu thiếu", "Risk", 0)],
        [("dependsOn", 0, 1, "Quy trình thanh toán phụ thuộc vào cổng đối soát"), ("supports", 1, 2, "Cổng đối soát hỗ trợ ledger nội bộ"), ("blocks", 3, 2, "Ledger nội bộ bị chặn bởi dữ liệu thiếu")], None),
    "004": ([
        ("監査計画", "Task", 0), ("証跡台帳", "Task", 0), ("保持方針", "Requirement", 0),
        ("古い記録の削除", "Task", 0)],
        [("dependsOn", 0, 1, "監査計画は証跡台帳に依存する"), ("implements", 1, 2, "証跡台帳は保持方針を実装する"), ("blocks", 2, 3, "保持方針は古い記録の削除を防ぐ")], None),
    "005": ([
        ("Review queue", "Task", 0), ("owner note", "ResearchFinding", 0),
        ("owner note", "ResearchFinding", 1), ("archive job", "Task", 0)],
        [("supports", 1, 0, "Owner note supports review queue"), ("blocks", 2, 3, "A second owner note blocks archive job")], None),
    "006": ([
        ("Policy label", "Constraint", 0), ("intake form", "Task", 0),
        ("Policy label", "Constraint", 1), ("audit form", "Task", 0),
        ("policy label", "Constraint", 2)],
        [("constrainedBy", 1, 0, "Policy label constrains intake form"), ("supports", 2, 3, "Policy label also supports audit form"), ("dependsOn", 3, 4, "Audit form dependsOn policy label")], None),
    "007": ([
        ("Cache refresh", "Task", 0), ("deploy", "Task", 0), ("release gate", "Requirement", 0)], [],
        ("partial", "The source negates blocking and explicitly forbids the proposed supports assertion; no positive relation is authorized.", ["Cache refresh blocks deploy", "Cache refresh supports release gate"])),
    "008": ([
        ("vendor portal", "Task", 0), ("billing rule", "Requirement", 0), ("payment", "Task", 0)], [],
        ("partial", "Both candidate relations are hedged or explicitly unclear, so entities are retained but relations are withheld.", ["vendor portal implements billing rule", "billing rule blocks payment"])),
    "009": ([
        ("Version 1 runbook", "Requirement", 0), ("old queue", "Task", 0),
        ("version 1 runbook", "Requirement", 0), ("Version 2 runbook", "Requirement", 0),
        ("current queue", "Task", 0),
    ], [("dependsOn", 4, 3, "The current queue dependsOn version 2 runbook")],
        ("partial", "The version-1 support statement is stale after supersession, and supersedes is not a released predicate.", ["Version 1 runbook supports the old queue", "Version 2 runbook supersedes version 1 runbook"])),
    "010": ([
        ("Yesterday's policy", "Requirement", 0), ("yesterday's policy", "Requirement", 0),
        ("legacy path", "Task", 0), ("Today's policy", "Requirement", 0),
        ("today's policy", "Requirement", 0), ("active path", "Task", 0),
    ], [("dependsOn", 5, 4, "The active path dependsOn today's policy")],
        ("partial", "The yesterday policy claim is stale after supersession, and supersedes is not a released predicate.", ["Yesterday's policy blocks the legacy path", "Today's policy supersedes yesterday's policy"])),
    "011": ([
        ("Design note", "ResearchFinding", 0), ("service boundary", "Constraint", 0),
        ("ingestion task", "Task", 0), ("schema check", "Requirement", 0)],
        [("supports", 1, 2, "That boundary supports the ingestion task"), ("dependsOn", 2, 3, "The ingestion task dependsOn the schema check")],
        ("partial", "The source uses names, which is not a released predicate; the grounded supports and dependsOn edges are retained.", ["Design note names the service boundary"])),
    "012": ([
        ("Data contract", "Requirement", 0), ("event stream", "Task", 0),
        ("event stream", "Task", 1), ("validation rule", "Requirement", 0),
        ("malformed payload", "Risk", 0)],
        [("implements", 2, 3, "The event stream implements validation rule"), ("blocks", 3, 4, "The validation rule blocks malformed payload")],
        ("partial", "Describes is not a released predicate, so only the two released grounded edges are materialized.", ["Data contract describes event stream"])),
    "013": ([
        ("Deployment plan", "Task", 0), ("release gate", "Requirement", 0),
        ("unverified artifact", "Risk", 0), ("checksum", "Requirement", 0)],
        [("implements", 0, 1, "Deployment plan implements release gate"), ("blocks", 1, 2, "Release gate blocks unverified artifact"), ("dependsOn", 2, 3, "Unverified artifact dependsOn checksum")], None),
    "014": ([
        ("Project brief", "ResearchFinding", 0), ("delivery plan", "Task", 0),
        ("delivery plan", "Task", 1), ("owner approval", "Requirement", 0),
        ("unauthorized launch", "Risk", 0)],
        [("supports", 0, 1, "Project brief supports delivery plan"), ("dependsOn", 2, 3, "Delivery plan dependsOn owner approval"), ("blocks", 3, 4, "Owner approval blocks unauthorized launch")],
        ("partial", "The news article mention is explicitly unrelated project evidence and is not used to create an edge.", ["news article supports delivery plan"])),
    "015": ([
        ("Ticket thanh toán", "Task", 0), ("billing rule", "Requirement", 0),
        ("Billing rule", "Requirement", 0), ("ledger chính", "Task", 0),
        ("Ledger chính", "Task", 0), ("giao dịch thiếu mã", "Risk", 0)],
        [("supports", 0, 1, "Ticket thanh toán supports billing rule"), ("dependsOn", 2, 3, "Billing rule phụ thuộc vào ledger chính"), ("blocks", 4, 5, "Ledger chính blocks giao dịch thiếu mã")], None),
    "016": ([
        ("監査メモ", "ResearchFinding", 0), ("audit queue", "Task", 0),
        ("証跡台帳", "Task", 0), ("証跡台帳", "Task", 1), ("削除予定", "Risk", 0)],
        [("supports", 0, 1, "監査メモ supports audit queue"), ("dependsOn", 1, 2, "Audit queue は証跡台帳に依存する"), ("blocks", 3, 4, "証跡台帳 blocks 削除予定")], None),
    "017": ([
        ("Résumé task", "Task", 0), ("café review", "Task", 0), ("Café review", "Task", 0),
        ("🧪 test note", "ResearchFinding", 0), ("Test note", "ResearchFinding", 0), ("stale build", "Risk", 0)],
        [("supports", 0, 1, "Résumé task supports café review"), ("dependsOn", 2, 3, "Café review dependsOn 🧪 test note"), ("blocks", 4, 5, "Test note blocks stale build")], None),
    "018": ([
        ("draft plan", "Task", 0), ("fallback plan", "Task", 0), ("migration", "Task", 0)], [],
        ("full", "The source gives an either/or hedge and explicitly says which plan is active is unidentified.", ["draft plan supports migration", "fallback plan supports migration"])),
    "019": ([], [],
        ("full", "The instruction text is explicitly data and establishes neither a relation nor tool authority.", ["provider call", "any asserted relation"])),
    "020": ([
        ("alpha", "Task", 0), ("Beta", "Task", 0), ("review", "Requirement", 0)],
        [("dependsOn", 1, 2, "Beta dependsOn review")],
        ("partial", "adjacentTo is explicitly unreleased and is quarantined; the released dependsOn edge is retained.", ["alpha adjacentTo beta"])),
    "021": ([
        ("shared task", "Task", 0), ("local task", "Task", 0), ("Local task", "Task", 0), ("owner check", "Requirement", 0)],
        [("dependsOn", 2, 3, "Local task dependsOn owner check")],
        ("partial", "The claimed supports edge is cross-project with unknown scope and is withheld; the local edge is grounded.", ["shared task supports local task"])),
    "022": ([
        ("old alert", "Risk", 0), ("current alert", "Risk", 0), ("current alert", "Risk", 1), ("deployment", "Task", 0)],
        [("blocks", 2, 3, "The current alert blocks deployment")],
        ("partial", "The source negates supersession and forbids inferring approval from silence; supersedes is also unreleased.", ["old alert supersedes current alert", "silence supports approval"])),
    "023": ([
        ("Service A", "Task", 0), ("Service B", "Task", 0), ("Service B", "Task", 1), ("release plan", "Task", 0)],
        [("supports", 2, 3, "Service B supports release plan")],
        ("partial", "relatesTo is explicitly unsupported and quarantined; the released supports edge is retained.", ["Service A relatesTo Service B"])),
    "024": ([
        ("Draft checklist", "Task", 0)], [],
        ("full", "The possible dependency names no owner, and the draft is explicitly stale; finalization is prohibited.", ["Draft checklist dependsOn unknown owner"])),
}


def make_response(case_id: str, raw: str) -> dict:
    num = case_id[-3:]
    entity_specs, relation_specs, abstention = CASES[num]
    entities = []
    for idx, (label, typ, occurrence) in enumerate(entity_specs):
        entities.append({"entityId": f"dh-{num}-e{idx + 1:02d}", "type": typ, "label": label, "evidence": span(raw, label, occurrence)})
    relations = []
    for idx, (predicate, source, target, quote) in enumerate(relation_specs):
        relations.append({"relationId": f"dh-{num}-r{idx + 1:02d}", "predicate": predicate, "sourceEntityId": entities[source]["entityId"], "targetEntityId": entities[target]["entityId"], "evidence": span(raw, quote)})
    if abstention is None:
        abst = {"status": "none", "abstentionReason": None, "withheldAssertions": []}
    else:
        mode, reason, withheld = abstention
        abst = {"status": mode, "abstentionReason": reason, "withheldAssertions": withheld}
    return {"schemaVersion": "dense-hard-output.v1", "projectScopeId": SCOPE, "entities": entities, "relations": relations, "abstention": abst}


def main() -> None:
    payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    payload_without_digest = dict(payload)
    payload_without_digest.pop("payloadDigest", None)
    expected = digest(payload_without_digest)
    if expected != payload["payloadDigest"]:
        raise ValueError("source payload digest does not match bytes")
    records = []
    for src in payload["records"]:
        response = make_response(src["caseId"], src["rawText"])
        source_digest = src["sourceDigest"]
        source_version_id = f"s12.dense-hard.{src['caseId']}.source.v1"
        source_version = {
            "sourceVersionId": source_version_id, "projectScopeId": SCOPE,
            "canonicalContentDigest": source_digest, "coordinateSystemVersion": "unicode-code-point-half-open.v1",
            "receiptDigest": digest({"receipt": src["caseId"], "sourceDigest": source_digest}),
            "canonicalizationVersion": "utf8-exact-source.v1", "contractVersion": "dense-hard-output.v1",
            "originalContentDigest": source_digest, "parentCanonicalContentDigest": None, "parentSourceVersionId": None,
            "replayKey": f"{source_version_id}:{source_digest}", "retention": {"expiresOn": None, "policy": "synthetic-source-only"},
            "sourceArtifactScopeId": SCOPE,
        }
        records.append({"caseId": src["caseId"], "scenarioId": src["scenarioId"], "language": src["language"], "sourceDigest": source_digest, "sourceVersion": source_version, "response": response, "responseDigest": digest(response)})
    candidate = {
        "artifactVersion": "s12.dense-hard.candidate.v1", "status": "CANDIDATE_FROZEN_SOURCE_ONLY", "candidateModel": "gpt-5.6-luna", "reasoning": "high", "agentCandidateCalls": 24, "providerCalls": 0,
        "payloadPath": "evaluation/sprint-12/internal-poc/dense-hard-v1/dense-hard-source-payload.v1.json", "payloadDigest": payload["payloadDigest"], "projectScopeId": SCOPE,
        "records": records, "goldIncluded": False, "priorReviewsIncluded": False, "heldOutInspection": False, "rawSensitiveDataIncluded": False, "reviewOrScoringPerformed": False,
        "nonClaims": ["No gold artifact, evaluator manifest, prior review, or score was inspected.", "No provider or external tool call was made.", "Predicates outside the released allowlist are withheld, not inferred."],
        "codeDigest": file_digest(HERE / "validate_dense_hard_candidate.py"),
    }
    candidate["candidateDigest"] = digest(candidate)
    OUT_PATH.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidatePath": str(OUT_PATH), "candidateDigest": candidate["candidateDigest"], "payloadDigest": payload["payloadDigest"], "codeDigest": candidate["codeDigest"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
