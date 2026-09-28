"""Author the fresh source-only dense-hard v4 benchmark (DH-13).

The generator contains only synthetic source and author-time gold/manifest
construction.  It never reads a candidate and never writes a v4 evaluation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v4"
TYPES = ("Task", "Requirement", "Constraint", "Risk", "System", "Project", "Document", "Question", "Decision", "Dataset", "Person", "Control", "Resource")
PREDICATES = ("dependsOn", "implements", "blocks", "supports", "validates", "tracks", "constrains", "supersedes", "requires", "answers", "contains")
SLICES = ("multi-hop", "multi-relation", "repeated-labels", "different-occurrences", "negation", "non-assertion", "abstention", "ambiguity", "temporal-supersession", "stale-statement", "mixed-unicode", "combining-mark", "emoji", "cross-sentence-dependency", "distractors", "cross-project", "unsupported-relation", "adversarial-instruction", "partial-abstention", "full-abstention", "long-context", "type-ambiguity", "proposition-boundary", "occurrence-scoring", "evidence-normalization", "safe-unsafe-mix")


@dataclass(frozen=True)
class Entity:
    key: str
    label: str
    type: str


@dataclass(frozen=True)
class Relation:
    predicate: str
    source: str
    target: str
    trigger: str
    sentence: str


@dataclass(frozen=True)
class Case:
    number: int
    text: str
    slices: tuple[str, ...]
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()
    language: str = "en"
    abstention: str = "none"
    reason: str | None = None
    quarantine: int = 0


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def anchor(text: str, phrase: str, occurrence: int = 1) -> dict[str, Any]:
    start = -1
    for _ in range(occurrence):
        start = text.index(phrase, start + 1)
    return {"startOffset": start, "endOffset": start + len(phrase), "text": phrase}


def E(key: str, label: str, type_name: str) -> Entity:
    return Entity(key, label, type_name)


def R(predicate: str, source: str, target: str, trigger: str, sentence: str) -> Relation:
    return Relation(predicate, source, target, trigger, sentence)


def cases() -> tuple[Case, ...]:
    # All text, labels, and identifiers are new v4 material; safe utility cases
    # deliberately carry two or more grounded propositions.
    rows = [
        ("Alder matrix requires copper gate. copper gate validates dune ledger.", ("multi-hop", "multi-relation", "occurrence-scoring"), (E("matrix", "Alder matrix", "Task"), E("gate", "copper gate", "Control"), E("ledger", "dune ledger", "Dataset")), (R("requires", "matrix", "gate", "requires", "Alder matrix requires copper gate"), R("validates", "gate", "ledger", "validates", "copper gate validates dune ledger"))),
        ("Bracken service implements violet rule. violet rule constrains summit route.", ("multi-hop", "multi-relation", "proposition-boundary"), (E("service", "Bracken service", "System"), E("rule", "violet rule", "Requirement"), E("route", "summit route", "Resource")), (R("implements", "service", "rule", "implements", "Bracken service implements violet rule"), R("constrains", "rule", "route", "constrains", "violet rule constrains summit route"))),
        ("Cobalt register tracks linen request. linen request blocks brittle export.", ("multi-hop", "multi-relation", "cross-sentence-dependency"), (E("register", "Cobalt register", "Dataset"), E("request", "linen request", "Requirement"), E("export", "brittle export", "Risk")), (R("tracks", "register", "request", "tracks", "Cobalt register tracks linen request"), R("blocks", "request", "export", "blocks", "linen request blocks brittle export"))),
        ("Drift memo contains amber decision. amber decision supports ferry permit.", ("multi-relation", "different-occurrences", "evidence-normalization"), (E("memo", "Drift memo", "Document"), E("decision", "amber decision", "Decision"), E("permit", "ferry permit", "Requirement")), (R("contains", "memo", "decision", "contains", "Drift memo contains amber decision"), R("supports", "decision", "permit", "supports", "amber decision supports ferry permit"))),
        ("Ember project depends on olive dataset. olive dataset answers harbor question.", ("multi-hop", "multi-relation", "proposition-boundary"), (E("project", "Ember project", "Project"), E("dataset", "olive dataset", "Dataset"), E("question", "harbor question", "Question")), (R("dependsOn", "project", "dataset", "depends on", "Ember project depends on olive dataset"), R("answers", "dataset", "question", "answers", "olive dataset answers harbor question"))),
        ("Fallow task requires silver control. silver control blocks cracked parcel.", ("multi-hop", "multi-relation", "distractors"), (E("task", "Fallow task", "Task"), E("control", "silver control", "Control"), E("parcel", "cracked parcel", "Risk")), (R("requires", "task", "control", "requires", "Fallow task requires silver control"), R("blocks", "control", "parcel", "blocks", "silver control blocks cracked parcel"))),
        ("Garnet brief contains cedar token. cedar token validates sealed crate. sealed crate tracks a scan.", ("multi-hop", "multi-relation", "long-context"), (E("brief", "Garnet brief", "Document"), E("token", "cedar token", "Requirement"), E("crate", "sealed crate", "Dataset"), E("scan", "a scan", "Control")), (R("contains", "brief", "token", "contains", "Garnet brief contains cedar token"), R("validates", "token", "crate", "validates", "cedar token validates sealed crate"), R("tracks", "crate", "scan", "tracks", "sealed crate tracks a scan"))),
        ("Hearth plan supports indigo lane. indigo lane requires north badge.", ("multi-hop", "multi-relation", "safe-unsafe-mix"), (E("plan", "Hearth plan", "Task"), E("lane", "indigo lane", "Resource"), E("badge", "north badge", "Control")), (R("supports", "plan", "lane", "supports", "Hearth plan supports indigo lane"), R("requires", "lane", "badge", "requires", "indigo lane requires north badge"))),
        ("Ivory archive supersedes the retired map. Ivory archive supports current review.", ("temporal-supersession", "stale-statement", "repeated-labels", "different-occurrences"), (E("archive", "Ivory archive", "Document"), E("map", "the retired map", "Dataset"), E("review", "current review", "Task")), (R("supersedes", "archive", "map", "supersedes", "Ivory archive supersedes the retired map"), R("supports", "archive", "review", "supports", "Ivory archive supports current review"))),
        ("Jasper plan governs the former dock. Jasper replacement governs the active dock.", ("temporal-supersession", "stale-statement", "repeated-labels", "different-occurrences"), (E("old", "Jasper plan", "Document"), E("former", "the former dock", "Resource"), E("new", "Jasper replacement", "Document"), E("active", "the active dock", "Resource")), (R("supports", "old", "former", "governs", "Jasper plan governs the former dock"), R("supports", "new", "active", "governs", "Jasper replacement governs the active dock"))),
        ("Kelp map supports routé audit. routé audit validates élan seal.", ("mixed-unicode", "combining-mark", "multi-relation"), (E("map", "Kelp map", "Document"), E("audit", "routé audit", "Requirement"), E("seal", "élan seal", "Control")), (R("supports", "map", "audit", "supports", "Kelp map supports routé audit"), R("validates", "audit", "seal", "validates", "routé audit validates élan seal")), "mixed"),
        ("Lumen 🛰️ chart supports launch 🧭 task. launch 🧭 task blocks unstable 🧪 freight.", ("mixed-unicode", "emoji", "multi-relation"), (E("chart", "Lumen 🛰️ chart", "Document"), E("task", "launch 🧭 task", "Task"), E("freight", "unstable 🧪 freight", "Risk")), (R("supports", "chart", "task", "supports", "Lumen 🛰️ chart supports launch 🧭 task"), R("blocks", "task", "freight", "blocks", "launch 🧭 task blocks unstable 🧪 freight")), "mixed"),
        ("Mallow card mentions Nacre card. Nacre card supports archive shelf, while Mallow card is a decoy.", ("distractors", "repeated-labels", "different-occurrences", "multi-relation"), (E("mallow", "Mallow card", "Document"), E("nacre", "Nacre card", "Document"), E("shelf", "archive shelf", "Resource")), (R("contains", "mallow", "nacre", "mentions", "Mallow card mentions Nacre card"), R("supports", "nacre", "shelf", "supports", "Nacre card supports archive shelf, while Mallow card is a decoy"))),
        ("Nopal bundle requires ivory route. A quiet aside mentions moss notebook. ivory route validates gate emblem.", ("long-context", "distractors", "multi-hop", "multi-relation"), (E("bundle", "Nopal bundle", "Task"), E("route", "ivory route", "Requirement"), E("aside", "A quiet aside", "Document"), E("notebook", "moss notebook", "Dataset"), E("token", "gate emblem", "Control")), (R("requires", "bundle", "route", "requires", "Nopal bundle requires ivory route"), R("contains", "aside", "notebook", "mentions", "A quiet aside mentions moss notebook"), R("validates", "route", "token", "validates", "ivory route validates gate emblem"))),
        ("Ocher plan depends on river book. river book validates audit key. audit key blocks hazard box.", ("long-context", "multi-hop", "multi-relation", "proposition-boundary"), (E("plan", "Ocher plan", "Task"), E("book", "river book", "Dataset"), E("key", "audit key", "Control"), E("box", "hazard box", "Risk")), (R("dependsOn", "plan", "book", "depends on", "Ocher plan depends on river book"), R("validates", "book", "key", "validates", "river book validates audit key"), R("blocks", "key", "box", "blocks", "audit key blocks hazard box"))),
        ("Parchment register contains teal answer. teal answer supports intake gate.", ("multi-relation", "occurrence-scoring", "evidence-normalization"), (E("register", "Parchment register", "Document"), E("answer", "teal answer", "Decision"), E("gate", "intake gate", "Requirement")), (R("contains", "register", "answer", "contains", "Parchment register contains teal answer"), R("supports", "answer", "gate", "supports", "teal answer supports intake gate"))),
        ("Quartz service implements red protocol. red protocol constrains ferry clock.", ("multi-hop", "multi-relation", "type-ambiguity"), (E("service", "Quartz service", "System"), E("protocol", "red protocol", "Requirement"), E("clock", "ferry clock", "Constraint")), (R("implements", "service", "protocol", "implements", "Quartz service implements red protocol"), R("constrains", "protocol", "clock", "constrains", "red protocol constrains ferry clock"))),
        ("Rattan note tracks blue case. blue case answers a review question.", ("cross-sentence-dependency", "multi-hop", "multi-relation"), (E("note", "Rattan note", "Document"), E("case", "blue case", "Dataset"), E("question", "a review question", "Question")), (R("tracks", "note", "case", "tracks", "Rattan note tracks blue case"), R("answers", "case", "question", "answers", "blue case answers a review question"))),
        ("Sable project requires amber control. amber control validates the final seal.", ("multi-hop", "multi-relation", "safe-unsafe-mix"), (E("project", "Sable project", "Project"), E("control", "amber control", "Control"), E("seal", "the final seal", "Control")), (R("requires", "project", "control", "requires", "Sable project requires amber control"), R("validates", "control", "seal", "validates", "amber control validates the final seal"))),
        ("Tamarind memo supports local lane. local lane blocks late courier.", ("multi-hop", "multi-relation", "stale-statement"), (E("memo", "Tamarind memo", "Document"), E("lane", "local lane", "Resource"), E("courier", "late courier", "Risk")), (R("supports", "memo", "lane", "supports", "Tamarind memo supports local lane"), R("blocks", "lane", "courier", "blocks", "local lane blocks late courier"))),
        ("Umber task contains violet checklist. violet checklist requires harbor stamp.", ("multi-hop", "multi-relation", "occurrence-scoring"), (E("task", "Umber task", "Task"), E("checklist", "violet checklist", "Requirement"), E("stamp", "harbor stamp", "Control")), (R("contains", "task", "checklist", "contains", "Umber task contains violet checklist"), R("requires", "checklist", "stamp", "requires", "violet checklist requires harbor stamp"))),
        ("Verdant archive supersedes old ledger. Verdant archive validates active key.", ("temporal-supersession", "multi-relation", "different-occurrences"), (E("archive", "Verdant archive", "Document"), E("ledger", "old ledger", "Dataset"), E("key", "active key", "Control")), (R("supersedes", "archive", "ledger", "supersedes", "Verdant archive supersedes old ledger"), R("validates", "archive", "key", "validates", "Verdant archive validates active key"))),
        ("Willow project supports cinder plan. cinder plan depends on harbor dataset.", ("multi-hop", "multi-relation", "cross-sentence-dependency"), (E("project", "Willow project", "Project"), E("plan", "cinder plan", "Task"), E("dataset", "harbor dataset", "Dataset")), (R("supports", "project", "plan", "supports", "Willow project supports cinder plan"), R("dependsOn", "plan", "dataset", "depends on", "cinder plan depends on harbor dataset"))),
        ("Xylo register validates jade mark. jade mark blocks rough cargo.", ("multi-hop", "multi-relation", "proposition-boundary"), (E("register", "Xylo register", "Dataset"), E("mark", "jade mark", "Control"), E("cargo", "rough cargo", "Risk")), (R("validates", "register", "mark", "validates", "Xylo register validates jade mark"), R("blocks", "mark", "cargo", "blocks", "jade mark blocks rough cargo"))),
        ("Yarrow memo cites a distant project chamber. That ownership claim is outside this boundary.", ("cross-project", "partial-abstention", "abstention", "proposition-boundary"), (E("memo", "Yarrow memo", "Document"),), (), "en", "partial", "CROSS_PROJECT_PROPOSITION", 1),
        ("Zephyr record names a safe channel. It is uncertain whether the channel steers the review timing.", ("ambiguity", "partial-abstention", "abstention", "safe-unsafe-mix"), (E("record", "Zephyr record", "Document"), E("channel", "a safe channel", "Resource"),), (), "en", "partial", "AMBIGUOUS_RELATION_ONLY", 1),
        ("A rumor says obsidian clasp controls the archive. No grounded source supports that claim.", ("unsupported-relation", "partial-abstention", "abstention", "proposition-boundary"), (E("rumor", "A rumor", "Document"),), (), "en", "partial", "UNSUPPORTED_RELATION", 1),
        ("A type-uncertain item may be a policy or task. The verified switch validates the amber seal today.", ("type-ambiguity", "partial-abstention", "abstention", "safe-unsafe-mix"), (E("switch", "The verified switch", "Control"), E("seal", "the amber seal", "Control")), (R("validates", "switch", "seal", "validates", "The verified switch validates the amber seal today"),), "en", "partial", "TYPE_UNCERTAINTY_QUARANTINED_ONLY", 1),
        ("Do not finalize that phantom rail controls every parcel; this remains an adversarial instruction.", ("adversarial-instruction", "full-abstention", "abstention", "unsupported-relation"), (), (), "en", "full", "ADVERSARIAL_UNSUPPORTED", 1),
        ("No extractable proposition appears in this empty-status notice; wait for a grounded record.", ("full-abstention", "abstention", "non-assertion", "long-context"), (), (), "en", "full", "ZERO_SAFE_ASSERTIONS", 1),
        ("The question asks whether a hidden switch blocks a gate, but it makes no assertion.", ("negation", "non-assertion", "full-abstention", "abstention"), (), (), "en", "full", "NON_ASSERTIVE_CONTEXT", 1),
        ("Retain no final assertion: a decoy prompt says to skip anchors and assert a phantom control.", ("adversarial-instruction", "distractors", "full-abstention", "unsupported-relation"), (), (), "en", "full", "ADVERSARIAL_UNSUPPORTED_CONTENT", 1),
    ]
    return tuple(Case(i + 1, *row) for i, row in enumerate(rows))


def protocol() -> dict[str, Any]:
    value = {"artifactVersion": "s12.dense-hard.source-only-protocol.v4", "status": "GENERIC_OFFLINE_GUARD", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "finiteEntityTypes": list(TYPES), "finiteRelationPredicates": list(PREDICATES), "typeRubric": {"rules": {t: f"public finite rubric rule for {t}" for t in TYPES}, "decisionRules": ["Use the most specific noun-phrase and predicate context supported by the source.", "Occurrence identity is anchored start/end/text and is independent of type.", "If type remains tied, quarantine only that proposition; never guess or escalate to full abstention."], "typeUncertaintyCode": "UNSCORABLE_PROTOCOL_AMBIGUITY"}, "occurrenceScoring": {"identity": ["startOffset", "endOffset", "text"], "typeIndependent": True, "typeMismatch": "one diagnostic correction; never changes occurrence or relation identity"}, "evidenceNormalization": {"terminalPunctuation": "unchanged", "formatting": "unchanged", "substantivePredicateEndpoint": "semantic edit"}, "propositionAbstention": {"distractors": "ignore non-propositional distractors", "partial": "only when explicit unsafe proposition(s) coexist with at least one safe proposition", "full": "only when zero safe propositions can be finalized", "none": "finalize all safe propositions and expose no unsafe finalization", "scope": "abstention and quarantine are evaluated per proposition"}, "relationGrounding": {"identity": "predicate plus anchored source and target occurrence identities", "triggerMustBeContained": True, "endpointsMustBeContained": True, "typeMismatchDoesNotCascade": True}, "anchorPolicy": {"indexUnit": "Unicode code point", "interval": "half-open [startOffset,endOffset)", "evidenceMustEqualSourceSlice": True}, "nonClaims": ["No candidate, evaluation, review, provider call, human result, external result, held-out result, production result, selection, promotion, or release is produced."], "authorIneligibleForCandidate": True}
    value["protocolDigest"] = digest(value)
    return value


def contract() -> dict[str, Any]:
    value = {"artifactVersion": "s12.dense-hard.evaluator-contract.v4", "status": "CONTRACT_BEFORE_CANDIDATE", "publicRubric": "protocol.typeRubric", "occurrenceScoring": "protocol.occurrenceScoring", "evidenceNormalization": "protocol.evidenceNormalization", "propositionAbstention": "protocol.propositionAbstention", "metrics": {"occurrence": "anchored occurrence precision/recall/F1", "type": "diagnostic correction count; ambiguity excluded", "relations": "predicate plus anchored endpoint occurrence precision/recall/F1", "abstention": "proposition-level full/partial exactness", "quarantine": "exact unsafe proposition precision/recall", "edits": "unchanged/minor/major/reject/abstain"}, "requiredBindings": ["sourcePayloadDigest", "goldDigest", "manifestDigest", "protocolDigest"], "noCandidateOrEvaluation": True, "nonClaims": ["This contract authorizes no candidate or evaluation and is synthetic offline material only."]}
    value["contractDigest"] = digest(value)
    return value


def schemas() -> dict[str, dict[str, Any]]:
    evidence = {"type": "object", "additionalProperties": False, "required": ["startOffset", "endOffset", "text"], "properties": {"startOffset": {"type": "integer", "minimum": 0}, "endOffset": {"type": "integer", "minimum": 1}, "text": {"type": "string", "minLength": 1}}}
    entity = {"type": "object", "additionalProperties": False, "required": ["entityId", "occurrenceKey", "type", "label", "evidence"], "properties": {"entityId": {"pattern": "^v4-[0-9]{3}-e[0-9]+$"}, "occurrenceKey": {"type": "string", "minLength": 1}, "type": {"enum": list(TYPES)}, "label": {"type": "string", "minLength": 1}, "evidence": evidence}}
    relation = {"type": "object", "additionalProperties": False, "required": ["relationId", "predicate", "sourceEntityId", "targetEntityId", "triggerEvidence", "evidence"], "properties": {"relationId": {"pattern": "^v4-[0-9]{3}-r[0-9]+$"}, "predicate": {"enum": list(PREDICATES)}, "sourceEntityId": {"type": "string"}, "targetEntityId": {"type": "string"}, "triggerEvidence": evidence, "evidence": evidence}}
    source_record = {"type": "object", "additionalProperties": False, "required": ["caseId", "scenarioId", "language", "slices", "rawText", "sourceDigest"], "properties": {"caseId": {"pattern": "^dh4-[0-9]{3}$"}, "scenarioId": {"pattern": "^dh4-s-[0-9]{3}$"}, "language": {"enum": ["en", "vi", "ja", "mixed"]}, "slices": {"type": "array", "minItems": 1, "items": {"enum": list(SLICES)}}, "rawText": {"type": "string", "minLength": 1}, "sourceDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}}}
    root = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False}
    source = dict(root, title="Dense-Hard v4 Source Only", required=["artifactVersion", "status", "datasetKind", "sourceOnly", "goldIncluded", "evaluatorManifestIncluded", "providerCalls", "heldOutInspection", "requiredOutputSchema", "records", "payloadDigest"], properties={"artifactVersion": {"const": "s12.dense-hard.source-payload.v4"}, "status": {"const": "FROZEN_SOURCE_ONLY_FOR_CANDIDATE"}, "datasetKind": {"const": "SYNTHETIC_NON_PRODUCTION"}, "sourceOnly": {"const": True}, "goldIncluded": {"const": False}, "evaluatorManifestIncluded": {"const": False}, "providerCalls": {"const": 0}, "heldOutInspection": {"const": False}, "requiredOutputSchema": {"type": "object", "additionalProperties": False, "required": ["schemaVersion", "protocolPath", "anchorRule", "abstentionRule"], "properties": {"schemaVersion": {"const": "dense-hard-output.v4"}, "protocolPath": {"const": "evaluation/sprint-12/internal-poc/dense-hard-v4/dense-hard-source-only-protocol.v4.json"}, "anchorRule": {"type": "string"}, "abstentionRule": {"type": "string"}}}, "records": {"type": "array", "minItems": 32, "maxItems": 32, "items": source_record}, "payloadDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}})
    expected = {"type": "object", "additionalProperties": False, "required": ["abstentionReason", "abstentionMode", "entities", "relations", "quarantineCount"], "properties": {"abstentionReason": {"type": ["string", "null"]}, "abstentionMode": {"enum": ["none", "partial", "full"]}, "entities": {"type": "array", "items": entity}, "relations": {"type": "array", "items": relation}, "quarantineCount": {"type": "integer", "minimum": 0}}}
    gold = dict(root, title="Dense-Hard v4 Private Gold", required=["artifactVersion", "sourcePayloadDigest", "records", "goldDigest"], properties={"artifactVersion": {"const": "s12.dense-hard.gold.v4"}, "sourcePayloadDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}, "records": {"type": "array", "minItems": 32, "maxItems": 32, "items": {"type": "object", "additionalProperties": False, "required": ["caseId", "expected"], "properties": {"caseId": {"pattern": "^dh4-[0-9]{3}$"}, "expected": expected}}}, "goldDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}})
    manifest_record = {"type": "object", "additionalProperties": False, "required": ["caseId", "scenarioId", "language", "slices", "expectedAbstention", "abstentionMode", "entityCount", "relationCount", "quarantineCount"], "properties": {"caseId": {"pattern": "^dh4-[0-9]{3}$"}, "scenarioId": {"pattern": "^dh4-s-[0-9]{3}$"}, "language": {"enum": ["en", "vi", "ja", "mixed"]}, "slices": {"type": "array", "minItems": 1, "items": {"enum": list(SLICES)}}, "expectedAbstention": {"type": "boolean"}, "abstentionMode": {"enum": ["none", "partial", "full"]}, "entityCount": {"type": "integer", "minimum": 0}, "relationCount": {"type": "integer", "minimum": 0}, "quarantineCount": {"type": "integer", "minimum": 0}}}
    manifest = dict(root, title="Dense-Hard v4 Private Manifest", required=["artifactVersion", "datasetKind", "sourcePayloadDigest", "goldDigest", "caseCount", "utilityCaseCount", "safetyCaseCount", "records", "manifestDigest"], properties={"artifactVersion": {"const": "s12.dense-hard.evaluator-manifest.v4"}, "datasetKind": {"const": "SYNTHETIC_NON_PRODUCTION"}, "sourcePayloadDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}, "goldDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}, "caseCount": {"const": 32}, "utilityCaseCount": {"const": 24}, "safetyCaseCount": {"const": 8}, "records": {"type": "array", "minItems": 32, "maxItems": 32, "items": manifest_record}, "manifestDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}})
    strict_obj = lambda required, properties: {"type": "object", "additionalProperties": False, "required": required, "properties": properties}
    protocol_schema = dict(root, title="Dense-Hard v4 Source-Only Protocol", required=["artifactVersion", "status", "datasetKind", "finiteEntityTypes", "finiteRelationPredicates", "typeRubric", "occurrenceScoring", "evidenceNormalization", "propositionAbstention", "relationGrounding", "anchorPolicy", "nonClaims", "authorIneligibleForCandidate", "protocolDigest"], properties={"artifactVersion": {"const": "s12.dense-hard.source-only-protocol.v4"}, "status": {"const": "GENERIC_OFFLINE_GUARD"}, "datasetKind": {"const": "SYNTHETIC_NON_PRODUCTION"}, "finiteEntityTypes": {"type": "array", "uniqueItems": True, "items": {"enum": list(TYPES)}}, "finiteRelationPredicates": {"type": "array", "uniqueItems": True, "items": {"enum": list(PREDICATES)}}, "typeRubric": strict_obj(["rules", "decisionRules", "typeUncertaintyCode"], {"rules": {"type": "object", "minProperties": 13, "additionalProperties": {"type": "string"}}, "decisionRules": {"type": "array", "minItems": 3, "items": {"type": "string"}}, "typeUncertaintyCode": {"const": "UNSCORABLE_PROTOCOL_AMBIGUITY"}}), "occurrenceScoring": strict_obj(["identity", "typeIndependent", "typeMismatch"], {"identity": {"const": ["startOffset", "endOffset", "text"]}, "typeIndependent": {"const": True}, "typeMismatch": {"type": "string"}}), "evidenceNormalization": strict_obj(["terminalPunctuation", "formatting", "substantivePredicateEndpoint"], {"terminalPunctuation": {"const": "unchanged"}, "formatting": {"const": "unchanged"}, "substantivePredicateEndpoint": {"type": "string"}}), "propositionAbstention": strict_obj(["distractors", "partial", "full", "none", "scope"], {key: {"type": "string"} for key in ["distractors", "partial", "full", "none", "scope"]}), "relationGrounding": strict_obj(["identity", "triggerMustBeContained", "endpointsMustBeContained", "typeMismatchDoesNotCascade"], {"identity": {"type": "string"}, "triggerMustBeContained": {"const": True}, "endpointsMustBeContained": {"const": True}, "typeMismatchDoesNotCascade": {"const": True}}), "anchorPolicy": strict_obj(["indexUnit", "interval", "evidenceMustEqualSourceSlice"], {"indexUnit": {"const": "Unicode code point"}, "interval": {"const": "half-open [startOffset,endOffset)"}, "evidenceMustEqualSourceSlice": {"const": True}}), "nonClaims": {"type": "array", "items": {"type": "string"}}, "authorIneligibleForCandidate": {"const": True}, "protocolDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}})
    contract_schema = dict(root, title="Dense-Hard v4 Evaluator Contract", required=["artifactVersion", "status", "publicRubric", "occurrenceScoring", "evidenceNormalization", "propositionAbstention", "metrics", "requiredBindings", "noCandidateOrEvaluation", "nonClaims", "contractDigest"], properties={"artifactVersion": {"const": "s12.dense-hard.evaluator-contract.v4"}, "status": {"const": "CONTRACT_BEFORE_CANDIDATE"}, "publicRubric": {"const": "protocol.typeRubric"}, "occurrenceScoring": {"const": "protocol.occurrenceScoring"}, "evidenceNormalization": {"const": "protocol.evidenceNormalization"}, "propositionAbstention": {"const": "protocol.propositionAbstention"}, "metrics": {"type": "object", "additionalProperties": False, "required": ["occurrence", "type", "relations", "abstention", "quarantine", "edits"], "properties": {key: {"type": "string"} for key in ["occurrence", "type", "relations", "abstention", "quarantine", "edits"]}}, "requiredBindings": {"const": ["sourcePayloadDigest", "goldDigest", "manifestDigest", "protocolDigest"]}, "noCandidateOrEvaluation": {"const": True}, "nonClaims": {"type": "array", "items": {"type": "string"}}, "contractDigest": {"pattern": "^sha256:[0-9a-f]{64}$"}})
    return {"dense-hard-source-payload.v4.schema.json": source, "dense-hard-gold.v4.schema.json": gold, "dense-hard-evaluator-manifest.v4.schema.json": manifest, "dense-hard-source-only-protocol.v4.schema.json": protocol_schema, "dense-hard-evaluator-contract.v4.schema.json": contract_schema}


def build() -> dict[str, dict[str, Any]]:
    source_records, gold_records, manifest_records = [], [], []
    for c in cases():
        cid = f"dh4-{c.number:03d}"
        source_records.append({"caseId": cid, "scenarioId": f"dh4-s-{c.number:03d}", "language": c.language, "slices": list(c.slices), "rawText": c.text, "sourceDigest": digest({"rawText": c.text})})
        entities, by_key = [], {}
        for spec in c.entities:
            for occurrence in range(1, c.text.count(spec.label) + 1):
                item = {"entityId": f"v4-{c.number:03d}-e{len(entities) + 1}", "occurrenceKey": f"{cid}#{spec.key}#{occurrence}", "type": spec.type, "label": spec.label, "evidence": anchor(c.text, spec.label, occurrence)}
                entities.append(item); by_key.setdefault(spec.key, []).append(item)
        relations = []
        for i, rel in enumerate(c.relations, 1):
            evidence = anchor(c.text, rel.sentence)
            trigger_start = evidence["startOffset"] + rel.sentence.index(rel.trigger)
            trigger = {"startOffset": trigger_start, "endOffset": trigger_start + len(rel.trigger), "text": rel.trigger}
            source = next(e for e in by_key[rel.source] if evidence["startOffset"] <= e["evidence"]["startOffset"] and e["evidence"]["endOffset"] <= evidence["endOffset"])
            target = next(e for e in by_key[rel.target] if evidence["startOffset"] <= e["evidence"]["startOffset"] and e["evidence"]["endOffset"] <= evidence["endOffset"])
            relations.append({"relationId": f"v4-{c.number:03d}-r{i}", "predicate": rel.predicate, "sourceEntityId": source["entityId"], "targetEntityId": target["entityId"], "triggerEvidence": trigger, "evidence": evidence})
        gold_records.append({"caseId": cid, "expected": {"abstentionReason": c.reason, "abstentionMode": c.abstention, "entities": entities, "relations": relations, "quarantineCount": c.quarantine}})
        manifest_records.append({"caseId": cid, "scenarioId": f"dh4-s-{c.number:03d}", "language": c.language, "slices": list(c.slices), "expectedAbstention": c.abstention != "none", "abstentionMode": c.abstention, "entityCount": len(entities), "relationCount": len(relations), "quarantineCount": c.quarantine})
    source = {"artifactVersion": "s12.dense-hard.source-payload.v4", "status": "FROZEN_SOURCE_ONLY_FOR_CANDIDATE", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "sourceOnly": True, "goldIncluded": False, "evaluatorManifestIncluded": False, "providerCalls": 0, "heldOutInspection": False, "requiredOutputSchema": {"schemaVersion": "dense-hard-output.v4", "protocolPath": "evaluation/sprint-12/internal-poc/dense-hard-v4/dense-hard-source-only-protocol.v4.json", "anchorRule": "zero-based Unicode code-point half-open offsets; exact evidence text", "abstentionRule": "proposition-level: ignore distractors, partial only with explicit unsafe plus safe, full only with zero safe"}, "records": source_records}
    source["payloadDigest"] = digest(source)
    gold = {"artifactVersion": "s12.dense-hard.gold.v4", "sourcePayloadDigest": source["payloadDigest"], "records": gold_records}; gold["goldDigest"] = digest(gold)
    manifest = {"artifactVersion": "s12.dense-hard.evaluator-manifest.v4", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "sourcePayloadDigest": source["payloadDigest"], "goldDigest": gold["goldDigest"], "caseCount": 32, "utilityCaseCount": 24, "safetyCaseCount": 8, "records": manifest_records}; manifest["manifestDigest"] = digest(manifest)
    return {"dense-hard-source-payload.v4.json": source, "dense-hard-gold.v4.json": gold, "dense-hard-evaluator-manifest.v4.json": manifest, "dense-hard-source-only-protocol.v4.json": protocol(), "dense-hard-evaluator-contract.v4.json": contract()}


def write(path: Path, value: object, refresh: bool = False) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and not refresh and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable artifact differs: {path}")
    path.write_text(content, encoding="utf-8")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--refresh", action="store_true"); args = parser.parse_args()
    PACKET.mkdir(parents=True, exist_ok=True)
    values = build(); values.update(schemas())
    for name, value in values.items(): write(PACKET / name, value, args.refresh)
    print(json.dumps({"status": "WRITTEN_SOURCE_GOLD_MANIFEST_PROTOCOL_CONTRACT", "caseCount": 32, "utilityCaseCount": 24, "safetyCaseCount": 8, "sourceDigest": values["dense-hard-source-payload.v4.json"]["payloadDigest"], "goldDigest": values["dense-hard-gold.v4.json"]["goldDigest"], "manifestDigest": values["dense-hard-evaluator-manifest.v4.json"]["manifestDigest"], "protocolDigest": values["dense-hard-source-only-protocol.v4.json"]["protocolDigest"], "contractDigest": values["dense-hard-evaluator-contract.v4.json"]["contractDigest"]}, sort_keys=True))


if __name__ == "__main__": main()
