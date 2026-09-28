"""Build the Sprint 12 dense-hard v2 source-only candidate.

This module is deliberately offline: it reads only the frozen source payload and
protocol packet, and emits deterministic source-grounded assertions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SOURCE_PATH = HERE / "dense-hard-source-payload.v2.json"
PROTOCOL_PATH = HERE / "dense-hard-source-only-protocol.v2.json"
SCHEMA_PATH = HERE / "dense-hard-candidate.v2.schema.json"
OUTPUT_PATH = HERE / "dense-hard-candidate.v2.json"

ENTITY_TYPES = {
    "Task", "Requirement", "Constraint", "Risk", "System", "Project",
    "Document", "Question", "Decision", "Dataset", "Person", "Control",
    "Resource",
}
PREDICATES = {
    "dependsOn", "implements", "blocks", "supports", "validates", "tracks",
    "constrains", "supersedes", "requires", "answers", "contains",
}


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def stable_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def anchor(text: str, quote: str, occurrence: int = 1) -> dict[str, Any]:
    """Return a zero-based Unicode-code-point half-open source span."""
    starts: list[int] = []
    cursor = 0
    while True:
        found = text.find(quote, cursor)
        if found < 0:
            break
        starts.append(found)
        cursor = found + 1
    if not starts or occurrence < 1 or occurrence > len(starts):
        raise ValueError(f"quote occurrence not found: {quote!r} #{occurrence}")
    start = starts[occurrence - 1]
    return {"startOffset": start, "endOffset": start + len(quote), "text": quote}


def entity(text: str, case_id: str, entities: list[dict[str, Any]], label: str, type_: str, occurrence: int = 1) -> str:
    entity_id = f"ent-{case_id}-{len(entities) + 1:02d}"
    key = f"{case_id}:occ-{len(entities) + 1:02d}"
    entities.append({
        "entityId": entity_id,
        "occurrenceKey": key,
        "type": type_,
        "label": label,
        "evidence": anchor(text, label, occurrence),
    })
    return entity_id


def relation(
    text: str,
    case_id: str,
    relations: list[dict[str, Any]],
    predicate: str,
    source_id: str,
    target_id: str,
    evidence_text: str,
    trigger: str,
    evidence_occurrence: int = 1,
) -> str:
    relation_id = f"rel-{case_id}-{len(relations) + 1:02d}"
    evidence = anchor(text, evidence_text, evidence_occurrence)
    trigger_evidence = anchor(text, trigger, evidence_occurrence)
    relations.append({
        "relationId": relation_id,
        "predicate": predicate,
        "sourceEntityId": source_id,
        "targetEntityId": target_id,
        "triggerEvidence": trigger_evidence,
        "evidence": evidence,
    })
    return relation_id


def quarantine(
    text: str,
    case_id: str,
    quarantined: list[dict[str, Any]],
    kind: str,
    reason: str,
    evidence_text: str,
    trigger: str | None = None,
) -> str:
    assertion_id = f"q-{case_id}-{len(quarantined) + 1:02d}"
    item: dict[str, Any] = {
        "assertionId": assertion_id,
        "kind": kind,
        "reasonCode": reason,
        "status": "quarantined",
        "evidence": anchor(text, evidence_text),
    }
    if trigger is not None:
        item["triggerEvidence"] = anchor(text, trigger)
    quarantined.append(item)
    return assertion_id


def response(record: dict[str, Any], mode: str, entities: list[dict[str, Any]], relations: list[dict[str, Any]], quarantined: list[dict[str, Any]]) -> dict[str, Any]:
    if mode == "none":
        abstention = {"mode": "none"}
    elif mode == "partial":
        abstention = {"mode": "partial", "reason": "at least one assertion is grounded while another is withheld"}
    else:
        abstention = {"mode": "full", "reason": "no assertion is finalized; proposed content is quarantined"}
    propositions: list[dict[str, Any]] = []
    for item in entities:
        propositions.append({"assertionId": item["entityId"], "kind": "entity", "status": "finalized", "entityId": item["entityId"]})
    for item in relations:
        propositions.append({"assertionId": item["relationId"], "kind": "relation", "status": "finalized", "relationId": item["relationId"]})
    for item in quarantined:
        propositions.append({"assertionId": item["assertionId"], "kind": item["kind"], "status": "quarantined"})
    return {
        "caseId": record["caseId"],
        "scenarioId": record["scenarioId"],
        "language": record["language"],
        "sourceDigest": record["sourceDigest"],
        "abstention": abstention,
        "entities": entities,
        "relations": relations,
        "quarantined": quarantined,
        "occurrenceRegistry": [
            {"occurrenceKey": item["occurrenceKey"], "entityId": item["entityId"], "label": item["label"], "evidence": item["evidence"]}
            for item in entities
        ],
        "propositionRegistry": propositions,
    }


def build_responses(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {record["caseId"]: record for record in records}
    out: list[dict[str, Any]] = []

    def make(case_id: str, mode: str, fn: Any) -> None:
        record = by_id[case_id]
        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []
        quarantined: list[dict[str, Any]] = []
        fn(record["rawText"], case_id, entities, relations, quarantined)
        out.append(response(record, mode, entities, relations, quarantined))

    def c001(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Harbor intake", "Requirement"); b = entity(t, c, e, "tide token", "Control", 1); d = entity(t, c, e, "cobalt ledger", "Document"); b2 = entity(t, c, e, "tide token", "Control", 2); x = entity(t, c, e, "unsafe export", "Constraint"); b3 = entity(t, c, e, "tide token", "Control", 3)
        relation(t, c, r, "dependsOn", a, b, "Harbor intake depends on tide token.", "depends on"); relation(t, c, r, "validates", d, b2, "The cobalt ledger validates tide token.", "validates"); relation(t, c, r, "blocks", b3, x, "The tide token blocks unsafe export.", "blocks")
    def c002(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Juniper checklist", "Requirement"); b = entity(t, c, e, "slate index", "Document", 1); b2 = entity(t, c, e, "slate index", "Document", 2); d = entity(t, c, e, "ferry permit", "Requirement", 1); d2 = entity(t, c, e, "ferry permit", "Requirement", 2); x = entity(t, c, e, "dock release", "Constraint")
        relation(t, c, r, "dependsOn", a, b, "Juniper checklist depends on slate index.", "depends on"); relation(t, c, r, "supports", b2, d, "The slate index supports ferry permit.", "supports"); relation(t, c, r, "constrains", d2, x, "The ferry permit constrains dock release.", "constrains")
    def c003(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Copper relay", "System"); b = entity(t, c, e, "kiln schema", "Requirement", 1); d = entity(t, c, e, "ember window", "Control", 1); b2 = entity(t, c, e, "kiln schema", "Requirement", 2); d2 = entity(t, c, e, "ember window", "Control", 2); x = entity(t, c, e, "rushed launch", "Risk")
        relation(t, c, r, "implements", a, b, "Copper relay implements kiln schema.", "implements"); relation(t, c, r, "tracks", b2, d, "The kiln schema tracks ember window.", "tracks"); relation(t, c, r, "blocks", d2, x, "The ember window blocks rushed launch.", "blocks")
    def c004(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Mica dossier", "Document"); b = entity(t, c, e, "north archive", "Resource", 1); d = entity(t, c, e, "audit query", "Question", 1); b2 = entity(t, c, e, "north archive", "Resource", 2); d2 = entity(t, c, e, "audit query", "Question", 2); x = entity(t, c, e, "seal register", "Control")
        relation(t, c, r, "requires", a, b, "Mica dossier requires north archive.", "requires"); relation(t, c, r, "answers", b2, d, "The north archive answers audit query.", "answers"); relation(t, c, r, "dependsOn", d2, x, "The audit query depends on seal register.", "depends on")
    def c005(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "aster memo", "Document", 1); b = entity(t, c, e, "river permit", "Requirement", 1); a2 = entity(t, c, e, "aster memo", "Document", 2); b2 = entity(t, c, e, "river permit", "Requirement", 2)
        quarantine(t, c, q, "relation", "UNSUPPORTED_PREDICATE", "The aster memo cites river permit.", "cites"); relation(t, c, r, "blocks", a2, b2, "A second aster memo blocks river permit.", "blocks")
    def c006(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Quartz label", "Control", 1); b = entity(t, c, e, "intake ledger", "Document"); a2 = entity(t, c, e, "Quartz label", "Control", 2); d = entity(t, c, e, "transit ledger", "Document", 1); d2 = entity(t, c, e, "transit ledger", "Document", 2); a3 = entity(t, c, e, "quartz label", "Control", 1)
        relation(t, c, r, "supports", a, b, "Quartz label supports intake ledger.", "supports"); relation(t, c, r, "constrains", a2, d, "Quartz label also constrains transit ledger.", "constrains"); relation(t, c, r, "requires", d2, a3, "The transit ledger requires quartz label.", "requires")
    def full_negated(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]], sentence: str, trigger: str) -> None:
        quarantine(t, c, q, "relation", "NEGATED", sentence, trigger)
    def c007(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        full_negated(t, c, e, r, q, "the blue warrant supports the gate", "supports")
    def c008(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        full_negated(t, c, e, r, q, "cedar switch implements the payment rule", "implements")
    def c009(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        entity(t, c, e, "Amber docket", "Document"); entity(t, c, e, "secure audit", "Requirement"); quarantine(t, c, q, "relation", "UNSUPPORTED_PREDICATE", "Amber docket records secure audit.", "records"); quarantine(t, c, q, "relation", "AMBIGUOUS", "amber docket governs remote archive", "governs")
    def c010(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        entity(t, c, e, "Violet plan", "Document"); entity(t, c, e, "winter queue", "Resource"); quarantine(t, c, q, "relation", "UNSUPPORTED_PREDICATE", "Violet plan names winter queue.", "names"); quarantine(t, c, q, "relation", "AMBIGUOUS", "winter queue blocks review timer", "blocks")
    def c011(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Old beacon policy", "Document"); b = entity(t, c, e, "current beacon policy", "Document", 1); b2 = entity(t, c, e, "current beacon policy", "Document", 2); d = entity(t, c, e, "fresh dispatch", "Requirement")
        relation(t, c, r, "supersedes", b, a, "Old beacon policy is superseded by current beacon policy.", "superseded"); relation(t, c, r, "supports", b2, d, "The current beacon policy supports fresh dispatch.", "supports")
    def c012(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        entity(t, c, e, "Retired map", "Document"); entity(t, c, e, "prior route", "Resource"); entity(t, c, e, "replacement map", "Document"); entity(t, c, e, "active route", "Resource"); quarantine(t, c, q, "relation", "STALE", "Retired map governed prior route.", "governed"); quarantine(t, c, q, "relation", "UNSUPPORTED_PREDICATE", "The replacement map governs active route.", "governs")
    def c013(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Sổ mây", "Document"); b = entity(t, c, e, "cầu lọc", "Control", 1); d = entity(t, c, e, "mã neo", "Control", 1); b2 = entity(t, c, e, "cầu lọc", "Control", 2); d2 = entity(t, c, e, "mã neo", "Control", 2); x = entity(t, c, e, "chuyến gửi lỗi", "Risk")
        relation(t, c, r, "dependsOn", a, b, "Sổ mây phụ thuộc vào cầu lọc.", "phụ thuộc vào"); relation(t, c, r, "validates", b2, d, "cầu lọc kiểm tra mã neo.", "kiểm tra"); relation(t, c, r, "blocks", d2, x, "mã neo chặn chuyến gửi lỗi.", "chặn")
    def c014(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "青い台帳", "Document"); b = entity(t, c, e, "港の規則", "Requirement", 1); d = entity(t, c, e, "検査印", "Control", 1); b2 = entity(t, c, e, "港の規則", "Requirement", 2); d2 = entity(t, c, e, "検査印", "Control", 2); x = entity(t, c, e, "遅延出荷", "Risk")
        relation(t, c, r, "supports", a, b, "青い台帳は港の規則を支える。", "支える"); relation(t, c, r, "requires", b2, d, "港の規則は検査印を必要とする。", "必要とする"); relation(t, c, r, "blocks", d2, x, "検査印は遅延出荷を止める。", "止める")
    def c015(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Café docket", "Document"); b = entity(t, c, e, "naivé review", "Requirement", 1); b2 = entity(t, c, e, "naivé review", "Requirement", 2); x = entity(t, c, e, "élan archive", "Resource")
        relation(t, c, r, "supports", a, b, "Café docket supports naivé review.", "supports"); relation(t, c, r, "blocks", b2, x, "The naivé review blocks élan archive.", "blocks")
    def c016(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Signal 🛰️ map", "Document"); b = entity(t, c, e, "launch 🧭 plan", "Requirement", 1); b2 = entity(t, c, e, "launch 🧭 plan", "Requirement", 2); x = entity(t, c, e, "unstable 🧪 cargo", "Risk")
        relation(t, c, r, "supports", a, b, "Signal 🛰️ map supports launch 🧭 plan.", "supports"); relation(t, c, r, "blocks", b2, x, "The launch 🧭 plan blocks unstable 🧪 cargo.", "blocks")
    def c017(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        entity(t, c, e, "Lumen brief", "Document"); b = entity(t, c, e, "harbor token", "Control", 1); d = entity(t, c, e, "sealed ledger", "Document", 1); b2 = entity(t, c, e, "harbor token", "Control", 2); d2 = entity(t, c, e, "sealed ledger", "Document", 2); x = entity(t, c, e, "inspection stamp", "Control"); quarantine(t, c, q, "relation", "UNSUPPORTED_PREDICATE", "Lumen brief names harbor token.", "names"); relation(t, c, r, "supports", b2, d, "The harbor token supports a sealed ledger across the next sentence.", "supports"); relation(t, c, r, "tracks", d2, x, "The sealed ledger tracks inspection stamp.", "tracks")
    def c018(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        p = entity(t, c, e, "Pine card", "Document", 1); s = entity(t, c, e, "Stone card", "Document", 1); p2 = entity(t, c, e, "pine card", "Document", 1); s2 = entity(t, c, e, "Stone card", "Document", 2); x = entity(t, c, e, "archive lane", "Resource"); quarantine(t, c, q, "relation", "UNSUPPORTED_PREDICATE", "Pine card mentions Stone card.", "mentions"); relation(t, c, r, "supports", s2, x, "The Stone card supports archive lane", "supports"); quarantine(t, c, q, "entity", "DISTRACTOR", "pine card remains a distractor", "distractor")
    def c019(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        quarantine(t, c, q, "relation", "CROSS_PROJECT", "Project amber states that project cobalt owns the vault", "owns")
    def c020(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        quarantine(t, c, q, "relation", "UNVERIFIED", "mirror key controls gate latch", "controls")
    def c021(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        quarantine(t, c, q, "relation", "ADVERSARIAL", "hollow token blocks every task", "blocks")
    def c022(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Northstar bundle", "Document"); b = entity(t, c, e, "ivory route", "Resource", 1); note = entity(t, c, e, "moss ledger", "Document"); d = entity(t, c, e, "ivory route", "Resource", 2); x = entity(t, c, e, "gate token", "Control", 1); x2 = entity(t, c, e, "gate token", "Control", 2); y = entity(t, c, e, "export crate", "Constraint"); relation(t, c, r, "requires", a, b, "Northstar bundle requires ivory route.", "requires"); quarantine(t, c, q, "relation", "UNSUPPORTED_PREDICATE", "A quiet note discusses unrelated moss ledger.", "discusses"); relation(t, c, r, "validates", d, x, "The ivory route validates gate token.", "validates"); relation(t, c, r, "blocks", x2, y, "The gate token blocks export crate.", "blocks")
    def c023(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "Bản ghi sương", "Document"); b = entity(t, c, e, "tuyến cảng", "Resource", 1); d = entity(t, c, e, "dấu niêm", "Control", 1); b2 = entity(t, c, e, "tuyến cảng", "Resource", 2); d2 = entity(t, c, e, "dấu niêm", "Control", 2); x = entity(t, c, e, "lô hàng lỗi", "Risk")
        relation(t, c, r, "supports", a, b, "Bản ghi sương hỗ trợ tuyến cảng.", "hỗ trợ"); relation(t, c, r, "validates", b2, d, "tuyến cảng kiểm tra dấu niêm.", "kiểm tra"); relation(t, c, r, "blocks", d2, x, "dấu niêm chặn lô hàng lỗi.", "chặn")
    def c024(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        a = entity(t, c, e, "白い計画", "Document"); b = entity(t, c, e, "河川台帳", "Resource", 1); d = entity(t, c, e, "監査鍵", "Control", 1); b2 = entity(t, c, e, "河川台帳", "Resource", 2); d2 = entity(t, c, e, "監査鍵", "Control", 2); x = entity(t, c, e, "危険な搬送", "Risk")
        relation(t, c, r, "dependsOn", a, b, "白い計画は河川台帳に依存する。", "依存する"); relation(t, c, r, "validates", b2, d, "河川台帳は監査鍵を検証する。", "検証する"); relation(t, c, r, "blocks", d2, x, "監査鍵は危険な搬送を止める。", "止める")
    def c025(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        entity(t, c, e, "Silver note", "Document"); entity(t, c, e, "safe corridor", "Resource", 1); entity(t, c, e, "safe corridor", "Resource", 2); entity(t, c, e, "closed gate", "Constraint"); quarantine(t, c, q, "relation", "UNSUPPORTED_PREDICATE", "Silver note records safe corridor.", "records"); quarantine(t, c, q, "relation", "NEGATED", "safe corridor supports closed gate", "supports")
    def c026(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        old = entity(t, c, e, "Earlier reed plan", "Document"); local = entity(t, c, e, "local queue", "Resource"); cur = entity(t, c, e, "Current reed plan", "Document"); remote = entity(t, c, e, "remote queue", "Resource", 1); remote2 = entity(t, c, e, "remote queue", "Resource", 2); late = entity(t, c, e, "late dispatch", "Risk"); quarantine(t, c, q, "relation", "STALE", "Earlier reed plan supported local queue.", "supported"); relation(t, c, r, "supports", cur, remote, "Current reed plan supports remote queue.", "supports"); relation(t, c, r, "blocks", remote2, late, "The remote queue blocks late dispatch.", "blocks")
    def c027(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        entity(t, c, e, "A note from project delta", "Document"); entity(t, c, e, "project delta", "Project"); entity(t, c, e, "project echo", "Project"); entity(t, c, e, "sealed room", "Resource"); quarantine(t, c, q, "relation", "CROSS_PROJECT", "project delta refers to project echo's sealed room", "refers to")
    def c028(t: str, c: str, e: list[dict[str, Any]], r: list[dict[str, Any]], q: list[dict[str, Any]]) -> None:
        quarantine(t, c, q, "relation", "ADVERSARIAL", "phantom rail controls all records", "controls")

    funcs: list[tuple[str, str, Any]] = [
        ("dh2-001", "none", c001), ("dh2-002", "none", c002), ("dh2-003", "none", c003), ("dh2-004", "none", c004),
        ("dh2-005", "partial", c005), ("dh2-006", "none", c006), ("dh2-007", "full", c007), ("dh2-008", "full", c008),
        ("dh2-009", "partial", c009), ("dh2-010", "partial", c010), ("dh2-011", "none", c011), ("dh2-012", "partial", c012),
        ("dh2-013", "none", c013), ("dh2-014", "none", c014), ("dh2-015", "none", c015), ("dh2-016", "none", c016),
        ("dh2-017", "partial", c017), ("dh2-018", "partial", c018), ("dh2-019", "full", c019), ("dh2-020", "full", c020),
        ("dh2-021", "full", c021), ("dh2-022", "partial", c022), ("dh2-023", "none", c023), ("dh2-024", "none", c024),
        ("dh2-025", "partial", c025), ("dh2-026", "partial", c026), ("dh2-027", "partial", c027), ("dh2-028", "full", c028),
    ]
    for case_id, mode, fn in funcs:
        make(case_id, mode, fn)
    return out


def build() -> dict[str, Any]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    records = source["records"]
    responses = build_responses(records)
    code_digest = digest_bytes(Path(__file__).read_bytes())
    result: dict[str, Any] = {
        "artifactVersion": "s12.dense-hard.candidate.v2",
        "schemaVersion": "dense-hard-output.v2",
        "datasetKind": "SYNTHETIC_NON_PRODUCTION",
        "status": "FROZEN_SOURCE_ONLY_CANDIDATE",
        "sourceOnly": True,
        "sourcePayloadPath": "evaluation/sprint-12/internal-poc/dense-hard-v2/dense-hard-source-payload.v2.json",
        "sourcePayloadDigest": source["payloadDigest"],
        "protocolPath": "evaluation/sprint-12/internal-poc/dense-hard-v2/dense-hard-source-only-protocol.v2.json",
        "protocolDigest": protocol["protocolDigest"],
        "candidateModel": "gpt-5.6-luna",
        "reasoning": "high",
        "agentCandidateCalls": 28,
        "providerCalls": 0,
        "goldIncluded": False,
        "priorReviewsIncluded": False,
        "scoring": False,
        "review": False,
        "codeDigest": code_digest,
        "candidateDigest": "",
        "responses": responses,
    }
    result["candidateDigest"] = digest_bytes(stable_bytes({**result, "candidateDigest": None}))
    return result


if __name__ == "__main__":
    OUTPUT_PATH.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT_PATH)
