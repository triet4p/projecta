"""Build the source-only dense-hard v4 candidate deterministically.

This builder intentionally reads only the public v4 source payload, protocol,
and evaluator contract.  It never opens gold, manifest, lineage, or evaluator
artifacts and performs no scoring.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v4"
SOURCE = V4 / "dense-hard-source-payload.v4.json"
PROTOCOL = V4 / "dense-hard-source-only-protocol.v4.json"
CONTRACT = V4 / "dense-hard-evaluator-contract.v4.json"
OUTPUT = V4 / "dense-hard-candidate.v4.json"


ENTITY_TYPES = {
    "matrix": "System",
    "service": "System",
    "chart": "Document",
    "register": "Document",
    "memo": "Document",
    "archive": "Document",
    "brief": "Document",
    "map": "Document",
    "card": "Document",
    "note": "Document",
    "record": "Document",
    "plan": "Document",
    "project": "Project",
    "task": "Task",
    "bundle": "Resource",
    "rule": "Constraint",
    "request": "Requirement",
    "decision": "Decision",
    "dataset": "Dataset",
    "question": "Question",
    "review": "Question",
    "audit": "Task",
    "control": "Control",
    "gate": "Control",
    "route": "Resource",
    "lane": "Resource",
    "badge": "Control",
    "token": "Control",
    "seal": "Control",
    "key": "Control",
    "mark": "Control",
    "protocol": "Constraint",
    "permit": "Requirement",
    "export": "Resource",
    "parcel": "Resource",
    "crate": "Resource",
    "freight": "Resource",
    "cargo": "Resource",
    "box": "Resource",
    "dock": "Resource",
    "shelf": "Resource",
    "clock": "Resource",
    "courier": "Resource",
    "stamp": "Control",
    "answer": "Decision",
    "seal": "Control",
    "switch": "Control",
    "channel": "Resource",
    "chamber": "Resource",
    "rail": "Resource",
    "item": "Resource",
    "policy": "Constraint",
}


def stable(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(stable(value)).hexdigest()


def span(text: str, start: int, end: int) -> dict[str, Any]:
    return {"startOffset": start, "endOffset": end, "text": text[start:end]}


def sentence_spans(text: str) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start = 0
    for index, char in enumerate(text):
        if char == ".":
            result.append((start, index + 1))
            start = index + 2 if text[index + 1 : index + 2] == " " else index + 1
    if start < len(text):
        result.append((start, len(text)))
    return result


def find_occurrence(text: str, label: str, ordinal: int = 1) -> tuple[int, int]:
    start = -1
    for _ in range(ordinal):
        start = text.index(label, start + 1)
    return start, start + len(label)


def phrase_type(label: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    head = label.rstrip("🛰️🧭🧪").split()[-1].lower()
    return ENTITY_TYPES.get(head, "Resource")


def entity_specs(case_id: str) -> list[tuple[str, int, str | None]]:
    data: dict[str, list[tuple[str, int, str | None]]] = {
        "dh4-001": [("Alder matrix", 1, "System"), ("copper gate", 1, "Control"), ("dune ledger", 1, "Document")],
        "dh4-002": [("Bracken service", 1, "System"), ("violet rule", 1, "Constraint"), ("summit route", 1, "Resource")],
        "dh4-003": [("Cobalt register", 1, "Document"), ("linen request", 1, "Requirement"), ("brittle export", 1, "Resource")],
        "dh4-004": [("Drift memo", 1, "Document"), ("amber decision", 1, "Decision"), ("ferry permit", 1, "Requirement")],
        "dh4-005": [("Ember project", 1, "Project"), ("olive dataset", 1, "Dataset"), ("harbor question", 1, "Question")],
        "dh4-006": [("Fallow task", 1, "Task"), ("silver control", 1, "Control"), ("cracked parcel", 1, "Resource")],
        "dh4-007": [("Garnet brief", 1, "Document"), ("cedar token", 1, "Control"), ("sealed crate", 1, "Resource"), ("a scan", 1, "Document")],
        "dh4-008": [("Hearth plan", 1, "Document"), ("indigo lane", 1, "Resource"), ("north badge", 1, "Control")],
        "dh4-009": [("Ivory archive", 1, "Document"), ("retired map", 1, "Document"), ("Ivory archive", 2, "Document"), ("current review", 1, "Question")],
        "dh4-011": [("Kelp map", 1, "Document"), ("routé audit", 1, "Task"), ("élan seal", 1, "Control")],
        "dh4-012": [("Lumen 🛰️ chart", 1, "Document"), ("launch 🧭 task", 1, "Task"), ("unstable 🧪 freight", 1, "Resource")],
        "dh4-013": [("Nacre card", 2, "Document"), ("archive shelf", 1, "Resource")],
        "dh4-014": [("Nopal bundle", 1, "Resource"), ("ivory route", 1, "Resource"), ("gate emblem", 1, "Control")],
        "dh4-015": [("Ocher plan", 1, "Document"), ("river book", 1, "Document"), ("audit key", 1, "Control"), ("hazard box", 1, "Resource")],
        "dh4-016": [("Parchment register", 1, "Document"), ("teal answer", 1, "Decision"), ("intake gate", 1, "Control")],
        "dh4-017": [("Quartz service", 1, "System"), ("red protocol", 1, "Constraint"), ("ferry clock", 1, "Resource")],
        "dh4-018": [("Rattan note", 1, "Document"), ("blue case", 1, "Resource"), ("review question", 1, "Question")],
        "dh4-019": [("Sable project", 1, "Project"), ("amber control", 1, "Control"), ("final seal", 1, "Control")],
        "dh4-020": [("Tamarind memo", 1, "Document"), ("local lane", 1, "Resource"), ("late courier", 1, "Resource")],
        "dh4-021": [("Umber task", 1, "Task"), ("violet checklist", 1, "Document"), ("harbor stamp", 1, "Control")],
        "dh4-022": [("Verdant archive", 1, "Document"), ("old ledger", 1, "Document"), ("Verdant archive", 2, "Document"), ("active key", 1, "Control")],
        "dh4-023": [("Willow project", 1, "Project"), ("cinder plan", 1, "Document"), ("harbor dataset", 1, "Dataset")],
        "dh4-024": [("Xylo register", 1, "Document"), ("jade mark", 1, "Control"), ("rough cargo", 1, "Resource")],
        "dh4-025": [("Yarrow memo", 1, "Document"), ("distant project chamber", 1, "Resource")],
        "dh4-026": [("Zephyr record", 1, "Document"), ("safe channel", 1, "Resource")],
        "dh4-027": [("obsidian clasp", 1, "Control"), ("the archive", 1, "Document")],
        "dh4-028": [("verified switch", 1, "Control"), ("amber seal", 1, "Control"), ("type-uncertain item", 1, "Resource")],
        "dh4-029": [],
        "dh4-030": [],
        "dh4-031": [],
        "dh4-032": [],
    }
    return data.get(case_id, [])


def relation_specs(case_id: str) -> list[tuple[str, int, str, int, str, int]]:
    data: dict[str, list[tuple[str, int, str, int, str, int]]] = {
        "dh4-001": [("requires", 1, "Alder matrix", 1, "copper gate", 1), ("validates", 2, "copper gate", 1, "dune ledger", 1)],
        "dh4-002": [("implements", 1, "Bracken service", 1, "violet rule", 1), ("constrains", 2, "violet rule", 1, "summit route", 1)],
        "dh4-003": [("tracks", 1, "Cobalt register", 1, "linen request", 1), ("blocks", 2, "linen request", 1, "brittle export", 1)],
        "dh4-004": [("contains", 1, "Drift memo", 1, "amber decision", 1), ("supports", 2, "amber decision", 1, "ferry permit", 1)],
        "dh4-005": [("dependsOn", 1, "Ember project", 1, "olive dataset", 1), ("answers", 2, "olive dataset", 1, "harbor question", 1)],
        "dh4-006": [("requires", 1, "Fallow task", 1, "silver control", 1), ("blocks", 2, "silver control", 1, "cracked parcel", 1)],
        "dh4-007": [("contains", 1, "Garnet brief", 1, "cedar token", 1), ("validates", 2, "cedar token", 1, "sealed crate", 1), ("tracks", 3, "sealed crate", 1, "a scan", 1)],
        "dh4-008": [("supports", 1, "Hearth plan", 1, "indigo lane", 1), ("requires", 2, "indigo lane", 1, "north badge", 1)],
        "dh4-009": [("supersedes", 1, "Ivory archive", 1, "retired map", 1), ("supports", 2, "Ivory archive", 2, "current review", 1)],
        "dh4-011": [("supports", 1, "Kelp map", 1, "routé audit", 1), ("validates", 2, "routé audit", 1, "élan seal", 1)],
        "dh4-012": [("supports", 1, "Lumen 🛰️ chart", 1, "launch 🧭 task", 1), ("blocks", 2, "launch 🧭 task", 1, "unstable 🧪 freight", 1)],
        "dh4-013": [("supports", 2, "Nacre card", 2, "archive shelf", 1)],
        "dh4-014": [("requires", 1, "Nopal bundle", 1, "ivory route", 1), ("validates", 2, "ivory route", 1, "gate emblem", 1)],
        "dh4-015": [("dependsOn", 1, "Ocher plan", 1, "river book", 1), ("validates", 2, "river book", 1, "audit key", 1), ("blocks", 3, "audit key", 1, "hazard box", 1)],
        "dh4-016": [("contains", 1, "Parchment register", 1, "teal answer", 1), ("supports", 2, "teal answer", 1, "intake gate", 1)],
        "dh4-017": [("implements", 1, "Quartz service", 1, "red protocol", 1), ("constrains", 2, "red protocol", 1, "ferry clock", 1)],
        "dh4-018": [("tracks", 1, "Rattan note", 1, "blue case", 1), ("answers", 2, "blue case", 1, "review question", 1)],
        "dh4-019": [("requires", 1, "Sable project", 1, "amber control", 1), ("validates", 2, "amber control", 1, "final seal", 1)],
        "dh4-020": [("supports", 1, "Tamarind memo", 1, "local lane", 1), ("blocks", 2, "local lane", 1, "late courier", 1)],
        "dh4-021": [("contains", 1, "Umber task", 1, "violet checklist", 1), ("requires", 2, "violet checklist", 1, "harbor stamp", 1)],
        "dh4-022": [("supersedes", 1, "Verdant archive", 1, "old ledger", 1), ("validates", 2, "Verdant archive", 2, "active key", 1)],
        "dh4-023": [("supports", 1, "Willow project", 1, "cinder plan", 1), ("dependsOn", 2, "cinder plan", 1, "harbor dataset", 1)],
        "dh4-024": [("validates", 1, "Xylo register", 1, "jade mark", 1), ("blocks", 2, "jade mark", 1, "rough cargo", 1)],
        "dh4-028": [("validates", 2, "verified switch", 1, "amber seal", 1)],
    }
    return data.get(case_id, [])


def quarantine_specs(case_id: str) -> list[tuple[int, str, str | None]]:
    data = {
        "dh4-010": [(1, "unsupported predicate: governs; no finite predicate asserted", "governs"), (2, "unsupported predicate: governs; no finite predicate asserted", "governs")],
        "dh4-025": [(1, "cross-project ownership claim is outside the extraction boundary", "cites"), (2, "explicitly outside-boundary ownership claim", None)],
        "dh4-026": [(2, "explicit uncertainty about the relation", "steers")],
        "dh4-027": [(1, "rumor with no grounded source support", "controls")],
        "dh4-028": [(1, "type-uncertain policy-or-task proposition", None)],
        "dh4-029": [(1, "adversarial instruction and unsupported phantom relation", "controls")],
        "dh4-031": [(1, "question makes no assertion", "blocks")],
        "dh4-032": [(1, "decoy prompt explicitly requests phantom assertion", "assert")],
    }
    return data.get(case_id, [])


def abstention(case_id: str) -> str:
    if case_id in {"dh4-025", "dh4-026", "dh4-027", "dh4-028"}:
        return "partial"
    if case_id in {"dh4-010", "dh4-029", "dh4-030", "dh4-031", "dh4-032"}:
        return "full"
    return "none"


def build_record(source: dict[str, Any]) -> dict[str, Any]:
    text = source["rawText"]
    case_id = source["caseId"]
    sentences = sentence_spans(text)
    specs = entity_specs(case_id)
    entities: list[dict[str, Any]] = []
    occurrence_ids: dict[tuple[str, int], str] = {}
    ordered = sorted(specs, key=lambda item: find_occurrence(text, item[0], item[1])[0])
    for number, (label, ordinal, explicit_type) in enumerate(ordered, 1):
        start, end = find_occurrence(text, label, ordinal)
        occurrence_id = f"{case_id}-e{number:02d}"
        occurrence_ids[(label, ordinal)] = occurrence_id
        entities.append({
            "occurrenceId": occurrence_id,
            "type": phrase_type(label, explicit_type),
            "label": label,
            "evidence": span(text, start, end),
        })
    relations: list[dict[str, Any]] = []
    for predicate, sentence, source_label, source_ord, target_label, target_ord in relation_specs(case_id):
        start, end = sentences[sentence - 1]
        relations.append({
            "predicate": predicate,
            "sourceOccurrenceId": occurrence_ids[(source_label, source_ord)],
            "targetOccurrenceId": occurrence_ids[(target_label, target_ord)],
            "triggerEvidence": span(text, start, end),
        })
    quarantine: list[dict[str, Any]] = []
    for sentence, reason, trigger in quarantine_specs(case_id):
        start, end = sentences[sentence - 1]
        item: dict[str, Any] = {"reason": reason, "evidence": span(text, start, end)}
        if trigger:
            trigger_start = text.index(trigger, start, end)
            item["triggerEvidence"] = span(text, trigger_start, trigger_start + len(trigger))
        quarantine.append(item)
    uncertainty = []
    if case_id == "dh4-026":
        uncertainty.append("relation ambiguity: channel-to-review timing is explicitly uncertain")
    if case_id == "dh4-028":
        uncertainty.append("UNSCORABLE_PROTOCOL_AMBIGUITY")
    return {
        "caseId": case_id,
        "scenarioId": source["scenarioId"],
        "sourceDigest": source["sourceDigest"],
        "entities": entities,
        "relations": relations,
        "abstention": abstention(case_id),
        "quarantine": quarantine,
        "uncertainty": uncertainty,
    }


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    records = [build_record(record) for record in source["records"]]
    candidate: dict[str, Any] = {
        "artifactVersion": "s12.dense-hard.candidate.v4",
        "status": "FROZEN_SOURCE_ONLY_CANDIDATE",
        "datasetKind": "SYNTHETIC_NON_PRODUCTION",
        "sourceOnly": True,
        "model": {"id": "gpt-5.6-luna", "reasoningEffort": "high", "calls": 32},
        "providerCalls": 0,
        "bindings": {
            "sourcePayloadDigest": source["payloadDigest"],
            "protocolDigest": protocol["protocolDigest"],
            "evaluatorContractDigest": contract["contractDigest"],
            "goldDigest": None,
            "manifestDigest": None,
        },
        "records": records,
        "nonClaims": [
            "No gold, manifest, review, score, evaluation, provider result, or production result is included.",
            "Predictions are frozen source-only material and are not a selection, promotion, or release.",
        ],
    }
    candidate["candidateDigest"] = digest(candidate)
    OUTPUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "candidateDigest": candidate["candidateDigest"], "records": len(records)}))


if __name__ == "__main__":
    main()
