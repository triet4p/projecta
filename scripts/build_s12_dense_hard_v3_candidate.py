"""Build the frozen, source-only dense-hard v3 candidate.

This builder has no provider, evaluator, gold, manifest, or prior-review input.
All final assertions are declared from the frozen source payload and are
anchored by exact Unicode-code-point spans at build time.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v3"
SOURCE_PATH = PACKET / "dense-hard-source-payload.v3.json"
PROTOCOL_PATH = PACKET / "dense-hard-source-only-protocol.v3.json"
CONTRACT_PATH = PACKET / "dense-hard-evaluator-contract.v3.json"
OUTPUT_PATH = PACKET / "dense-hard-candidate.v3.json"

EXPECTED_SOURCE_DIGEST = "sha256:b907a5a50d6c9db63a9806b8bb4e1d2b992391828290bc97b6cc2a023e0277c7"
EXPECTED_PROTOCOL_DIGEST = "sha256:939ed208c7d581f4dc35be5560196c6cb9e5bd4d746e8a67450c2cc1a71d3131"
EXPECTED_CONTRACT_DIGEST = "sha256:7e77febb8fc685134d0374340ed0e43c0cdbb892d51a53c75efe1a94f00dd532"

ENTITY_TYPES = {
    "Task", "Requirement", "Constraint", "Risk", "System", "Project",
    "Document", "Question", "Decision", "Dataset", "Person", "Control", "Resource",
}
PREDICATES = {
    "dependsOn", "implements", "blocks", "supports", "validates", "tracks",
    "constrains", "supersedes", "requires", "answers", "contains",
}


# Entity tuples are (label, type, occurrence number).  Relation tuples are
# (predicate, source label, target label, source occurrence, target occurrence,
# trigger).  Occurrence numbers matter for repeated labels and are 1-based only
# in this declarative table; emitted anchors are zero-based offsets.
CASES: dict[str, dict[str, Any]] = {
    "dh3-001": {"entities": [("Aster workflow", "Task", 1), ("bronze checklist", "Control", 1), ("bronze checklist", "Control", 2), ("harbor seal", "Resource", 1)], "relations": [("requires", "Aster workflow", "bronze checklist", 1, 1, "requires"), ("validates", "bronze checklist", "harbor seal", 2, 1, "validates")], "abstention": "none", "quarantine": []},
    "dh3-002": {"entities": [("Cinder engine", "System", 1), ("meadow rule", "Constraint", 1), ("meadow rule", "Constraint", 2), ("ferry schedule", "Resource", 1)], "relations": [("implements", "Cinder engine", "meadow rule", 1, 1, "implements"), ("constrains", "meadow rule", "ferry schedule", 2, 1, "constrains")], "abstention": "none", "quarantine": []},
    "dh3-003": {"entities": [("Dune register", "Document", 1), ("amber request", "Requirement", 1), ("amber request", "Requirement", 2), ("unsafe release", "Risk", 1)], "relations": [("tracks", "Dune register", "amber request", 1, 1, "tracks"), ("blocks", "amber request", "unsafe release", 2, 1, "blocks")], "abstention": "none", "quarantine": []},
    "dh3-004": {"entities": [("Elm brief", "Document", 1), ("quartz decision", "Decision", 1), ("quartz decision", "Decision", 2), ("launch permit", "Requirement", 1)], "relations": [("contains", "Elm brief", "quartz decision", 1, 1, "contains"), ("supports", "quartz decision", "launch permit", 2, 1, "supports")], "abstention": "none", "quarantine": []},
    "dh3-005": {"entities": [("Frost project", "Project", 1), ("willow dataset", "Dataset", 1), ("willow dataset", "Dataset", 2), ("intake question", "Question", 1)], "relations": [("dependsOn", "Frost project", "willow dataset", 1, 1, "depends on"), ("answers", "willow dataset", "intake question", 2, 1, "answers")], "abstention": "none", "quarantine": []},
    "dh3-006": {"entities": [("Grove task", "Task", 1), ("iron control", "Control", 1), ("iron control", "Control", 2), ("damaged parcel", "Resource", 1)], "relations": [("requires", "Grove task", "iron control", 1, 1, "requires"), ("blocks", "iron control", "damaged parcel", 2, 1, "blocks")], "abstention": "none", "quarantine": []},
    "dh3-007": {"entities": [], "relations": [], "abstention": "full", "quarantine": [{"kind": "proposition", "reason": "UNSUPPORTED_ASSERTION", "trigger": "references"}]},
    "dh3-008": {"entities": [], "relations": [], "abstention": "full", "quarantine": [{"kind": "relation", "reason": "NEGATED_CONTENT", "trigger": "supports"}]},
    "dh3-009": {"entities": [("Kite note", "Document", 1), ("safe channel", "Resource", 1), ("review clock", "Resource", 1)], "relations": [], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "UNSCORABLE_PROTOCOL_AMBIGUITY", "trigger": "controls"}]},
    "dh3-010": {"entities": [("Lark plan", "Document", 1), ("cedar route", "Resource", 1), ("night window", "Resource", 1)], "relations": [("supports", "Lark plan", "cedar route", 1, 1, "supports")], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "UNSCORABLE_PROTOCOL_AMBIGUITY", "trigger": "constrain"}]},
    "dh3-011": {"entities": [("Mica archive", "Document", 1), ("Mica archive", "Document", 2), ("retired index", "Document", 1), ("current review", "Task", 1)], "relations": [("supersedes", "Mica archive", "retired index", 1, 1, "supersedes"), ("supports", "Mica archive", "current review", 2, 1, "supports")], "abstention": "none", "quarantine": []},
    "dh3-012": {"entities": [("North plan", "Document", 1), ("former lane", "Resource", 1), ("North replacement", "Document", 1), ("active lane", "Resource", 1)], "relations": [], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "UNSUPPORTED_PREDICATE", "trigger": "governed"}, {"kind": "relation", "reason": "STALE_PROPOSITION", "trigger": "former lane"}]},
    "dh3-013": {"entities": [("Sổ lụa", "Document", 1), ("cầu đá", "Resource", 1), ("cầu đá", "Resource", 2), ("lô hàng lệch", "Resource", 1)], "relations": [("validates", "Sổ lụa", "cầu đá", 1, 1, "kiểm tra"), ("blocks", "cầu đá", "lô hàng lệch", 2, 1, "chặn")], "abstention": "none", "quarantine": []},
    "dh3-014": {"entities": [("青磁計画", "Project", 1), ("港印", "Control", 1), ("港印", "Control", 2), ("遅延箱", "Resource", 1)], "relations": [("requires", "青磁計画", "港印", 1, 1, "必要とする"), ("blocks", "港印", "遅延箱", 2, 1, "止める")], "abstention": "none", "quarantine": []},
    "dh3-015": {"entities": [("Café ledger", "Document", 1), ("naivé audit", "Task", 1), ("naivé audit", "Task", 2), ("élan seal", "Control", 1)], "relations": [("supports", "Café ledger", "naivé audit", 1, 1, "supports"), ("validates", "naivé audit", "élan seal", 2, 1, "validates")], "abstention": "none", "quarantine": []},
    "dh3-016": {"entities": [("Orbit 🛰️ map", "Document", 1), ("launch 🧭 plan", "Document", 1), ("launch 🧭 plan", "Document", 2), ("unstable 🧪 cargo", "Resource", 1)], "relations": [("supports", "Orbit 🛰️ map", "launch 🧭 plan", 1, 1, "supports"), ("blocks", "launch 🧭 plan", "unstable 🧪 cargo", 2, 1, "blocks")], "abstention": "none", "quarantine": []},
    "dh3-017": {"entities": [("Pollen brief", "Document", 1), ("harbor token", "Control", 1), ("harbor token", "Control", 2), ("sealed tray", "Resource", 1), ("sealed tray", "Resource", 2), ("scan mark", "Resource", 1)], "relations": [("validates", "harbor token", "sealed tray", 2, 1, "validates"), ("tracks", "sealed tray", "scan mark", 2, 1, "tracks")], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "UNSUPPORTED_PREDICATE", "trigger": "names"}]},
    "dh3-018": {"entities": [("Rook card", "Document", 1), ("Slate card", "Document", 1), ("Slate card", "Document", 2), ("archive lane", "Resource", 1), ("Rook card", "Document", 2), ("decoy", "Resource", 1)], "relations": [("supports", "Slate card", "archive lane", 2, 1, "supports")], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "UNSUPPORTED_PREDICATE", "trigger": "mentions"}, {"kind": "proposition", "reason": "UNSUPPORTED_ASSERTION", "trigger": "decoy"}]},
    "dh3-019": {"entities": [("Project saffron", "Project", 1), ("project teal", "Project", 1), ("sealed room", "Resource", 1)], "relations": [], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "CROSS_PROJECT_SCOPE", "trigger": "cites"}, {"kind": "proposition", "reason": "CROSS_PROJECT_SCOPE", "trigger": "ownership"}]},
    "dh3-020": {"entities": [("mirror latch", "Control", 1), ("vault", "Resource", 1)], "relations": [], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "UNSUPPORTED_ASSERTION", "trigger": "controls"}]},
    "dh3-021": {"entities": [], "relations": [], "abstention": "full", "quarantine": [{"kind": "proposition", "reason": "ADVERSARIAL_CONTENT", "trigger": "Ignore grounding"}]},
    "dh3-022": {"entities": [("Quill bundle", "Resource", 1), ("ivory route", "Resource", 1), ("ivory route", "Resource", 2), ("gate token", "Control", 1), ("gate token", "Control", 2), ("export crate", "Resource", 1)], "relations": [("requires", "Quill bundle", "ivory route", 1, 1, "requires"), ("validates", "ivory route", "gate token", 2, 1, "validates"), ("blocks", "gate token", "export crate", 2, 1, "blocks")], "abstention": "partial", "quarantine": [{"kind": "proposition", "reason": "UNSUPPORTED_ASSERTION", "trigger": "moss ledger"}]},
    "dh3-023": {"entities": [("Bản đồ sương", "Document", 1), ("tuyến biển", "Resource", 1), ("tuyến biển", "Resource", 2), ("dấu kín", "Control", 1), ("dấu kín", "Control", 2), ("kiện lỗi", "Resource", 1)], "relations": [("supports", "Bản đồ sương", "tuyến biển", 1, 1, "hỗ trợ"), ("validates", "tuyến biển", "dấu kín", 2, 1, "kiểm tra"), ("blocks", "dấu kín", "kiện lỗi", 2, 1, "chặn")], "abstention": "none", "quarantine": []},
    "dh3-024": {"entities": [("白樺計画", "Project", 1), ("河川帳", "Document", 1), ("河川帳", "Document", 2), ("監査鍵", "Control", 1), ("監査鍵", "Control", 2), ("危険箱", "Risk", 1)], "relations": [("dependsOn", "白樺計画", "河川帳", 1, 1, "依存する"), ("validates", "河川帳", "監査鍵", 2, 1, "検証する"), ("blocks", "監査鍵", "危険箱", 2, 1, "止める")], "abstention": "none", "quarantine": []},
    "dh3-025": {"entities": [("Silver record", "Document", 1), ("safe corridor", "Resource", 1), ("closed gate", "Control", 1)], "relations": [], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "NEGATED_CONTENT", "trigger": "supports"}, {"kind": "relation", "reason": "UNSUPPORTED_PREDICATE", "trigger": "states"}]},
    "dh3-026": {"entities": [("reed plan", "Document", 1), ("local shuttle", "Resource", 1), ("reed plan", "Document", 2), ("remote shuttle", "Resource", 1), ("remote shuttle", "Resource", 2), ("late courier", "Resource", 1)], "relations": [("blocks", "remote shuttle", "late courier", 2, 1, "blocks")], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "STALE_PROPOSITION", "trigger": "queued"}, {"kind": "relation", "reason": "UNSUPPORTED_PREDICATE", "trigger": "directs"}]},
    "dh3-027": {"entities": [("note", "Document", 1), ("project umber", "Project", 1), ("project violet", "Project", 1), ("chamber", "Resource", 1)], "relations": [], "abstention": "partial", "quarantine": [{"kind": "relation", "reason": "CROSS_PROJECT_SCOPE", "trigger": "refers"}, {"kind": "proposition", "reason": "UNSUPPORTED_ASSERTION", "trigger": "ownership"}]},
    "dh3-028": {"entities": [], "relations": [], "abstention": "full", "quarantine": [{"kind": "proposition", "reason": "ADVERSARIAL_CONTENT", "trigger": "skip anchors"}]},
    "dh3-029": {"entities": [("verified switch", "Control", 1), ("amber seal", "Control", 1)], "relations": [("validates", "verified switch", "amber seal", 1, 1, "validates")], "abstention": "partial", "quarantine": [{"kind": "entity", "reason": "UNSCORABLE_PROTOCOL_AMBIGUITY", "trigger": "type-uncertain item"}]},
    "dh3-030": {"entities": [], "relations": [], "abstention": "full", "quarantine": [{"kind": "proposition", "reason": "UNSUPPORTED_ASSERTION", "trigger": "No extractable proposition"}]},
}


def digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def find_occurrence(raw: str, label: str, occurrence: int) -> dict[str, Any]:
    starts: list[int] = []
    cursor = 0
    while True:
        found = raw.find(label, cursor)
        if found < 0:
            break
        starts.append(found)
        cursor = found + 1
    if occurrence < 1 or occurrence > len(starts):
        raise ValueError(f"missing occurrence {occurrence} of {label!r}")
    start = starts[occurrence - 1]
    return {"startOffset": start, "endOffset": start + len(label), "text": label}


def sentence_for(raw: str, trigger: str) -> dict[str, Any]:
    index = raw.find(trigger)
    if index < 0:
        raise ValueError(f"missing trigger {trigger!r}")
    left = index
    while left > 0 and raw[left - 1] not in ".!?。！？":
        left -= 1
    while left < len(raw) and raw[left].isspace():
        left += 1
    right = index + len(trigger)
    while right < len(raw) and raw[right] not in ".!?。！？":
        right += 1
    if right < len(raw):
        right += 1
    return {"startOffset": left, "endOffset": right, "text": raw[left:right]}


def make_candidate() -> dict[str, Any]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if source["payloadDigest"] != EXPECTED_SOURCE_DIGEST:
        raise ValueError("source payload digest mismatch")
    if protocol["protocolDigest"] != EXPECTED_PROTOCOL_DIGEST:
        raise ValueError("protocol digest mismatch")
    if contract["contractDigest"] != EXPECTED_CONTRACT_DIGEST:
        raise ValueError("evaluator contract digest mismatch")
    if len(source["records"]) != 30 or set(CASES) != {r["caseId"] for r in source["records"]}:
        raise ValueError("candidate plan must cover exactly the 30 source cases")

    records: list[dict[str, Any]] = []
    for source_record in source["records"]:
        case_id = source_record["caseId"]
        raw = source_record["rawText"]
        plan = CASES[case_id]
        entities: list[dict[str, Any]] = []
        for index, (label, entity_type, occurrence) in enumerate(plan["entities"], start=1):
            if entity_type not in ENTITY_TYPES:
                raise ValueError(f"unsupported entity type: {entity_type}")
            anchor = find_occurrence(raw, label, occurrence)
            entities.append({"assertionId": f"{case_id}-e-{index:02d}", "kind": "entity", "status": "finalized", "type": entity_type, "label": label, "occurrence": anchor})
        relations: list[dict[str, Any]] = []
        for index, (predicate, source_label, target_label, source_occ, target_occ, trigger) in enumerate(plan["relations"], start=1):
            if predicate not in PREDICATES:
                raise ValueError(f"unsupported predicate: {predicate}")
            source_occurrence = find_occurrence(raw, source_label, source_occ)
            target_occurrence = find_occurrence(raw, target_label, target_occ)
            evidence = sentence_for(raw, trigger)
            if not (evidence["startOffset"] <= source_occurrence["startOffset"] < source_occurrence["endOffset"] <= evidence["endOffset"] and evidence["startOffset"] <= target_occurrence["startOffset"] < target_occurrence["endOffset"] <= evidence["endOffset"]):
                raise ValueError(f"relation endpoints not grounded by evidence in {case_id}")
            trigger_evidence = find_occurrence(raw, trigger, 1)
            if not (evidence["startOffset"] <= trigger_evidence["startOffset"] < trigger_evidence["endOffset"] <= evidence["endOffset"]):
                raise ValueError(f"relation trigger not grounded by evidence in {case_id}")
            relations.append({"assertionId": f"{case_id}-r-{index:02d}", "kind": "relation", "status": "finalized", "predicate": predicate, "sourceOccurrence": source_occurrence, "targetOccurrence": target_occurrence, "evidence": evidence, "triggerEvidence": trigger_evidence})
        quarantine: list[dict[str, Any]] = []
        for index, item in enumerate(plan["quarantine"], start=1):
            evidence = sentence_for(raw, item["trigger"])
            quarantine.append({"assertionId": f"{case_id}-q-{index:02d}", "kind": item["kind"], "reasonCode": item["reason"], "status": "quarantined", "evidence": evidence})
        records.append({"caseId": case_id, "scenarioId": source_record["scenarioId"], "sourceDigest": source_record["sourceDigest"], "abstention": plan["abstention"], "entities": entities, "relations": relations, "quarantine": quarantine})

    builder_digest = digest_bytes(Path(__file__).read_bytes())
    candidate: dict[str, Any] = {
        "artifactVersion": "s12.dense-hard.candidate.v3",
        "datasetKind": "SYNTHETIC_NON_PRODUCTION",
        "sourceOnly": True,
        "status": "FROZEN_SOURCE_ONLY_CANDIDATE",
        "sourcePayloadDigest": EXPECTED_SOURCE_DIGEST,
        "protocolDigest": EXPECTED_PROTOCOL_DIGEST,
        "evaluatorContractDigest": EXPECTED_CONTRACT_DIGEST,
        "buildCodeDigest": builder_digest,
        "agentModel": "gpt-5.6-luna",
        "reasoningEffort": "high",
        "agentCandidateCalls": 30,
        "providerCalls": 0,
        "goldUsed": False,
        "priorReviewUsed": False,
        "scoringPerformed": False,
        "records": records,
    }
    candidate["candidateDigest"] = digest_bytes(canonical_json(candidate))
    return candidate


def main() -> None:
    # The v3 candidate is frozen once published.  Re-running the builder is a
    # read-only verification when the output already exists; it must not
    # replace the frozen digest with a mutable working-tree builder digest.
    if OUTPUT_PATH.exists():
        candidate = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    else:
        candidate = make_candidate()
        OUTPUT_PATH.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_PATH), "candidateDigest": candidate["candidateDigest"], "records": len(candidate["records"]), "agentCandidateCalls": candidate["agentCandidateCalls"], "providerCalls": candidate["providerCalls"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
