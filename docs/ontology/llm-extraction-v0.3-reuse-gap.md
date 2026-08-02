# M3 LLM Extraction v0.3 Reuse/Gap Matrix

**Status:** REVIEWED_AND_APPROVED (2026-08-02)
**Task:** S5-04
**Audit scope:** Released local ontology v0.3.0, its shapes, named-graph
contract, M2 competency queries, and Semantic Core candidate validation.

## Reuse and Gap Matrix

| M3 field/question | Released reuse | Shape/query evidence | Result |
|---|---|---|---|
| Trusted project scope | `projecta:belongsToProject`, project-scoped graph routing | `CandidateShape`, isolation shapes, CQ-SCOPE/CQ-ISO | Reuse |
| Immutable raw note and source evidence | `projecta:Note`, `projecta:rawText`, `NoteItem`, `contentText` | `NoteShape`, `NoteItemShape`, M2 source/evidence queries | Reuse |
| Exact Unicode evidence span | `projecta:evidenceStartOffset`, `projecta:evidenceEndOffset` | Evidence shapes and M2 offset queries | Reuse |
| Candidate lifecycle/review | `projecta:Candidate`, `candidateStatus`, lifecycle individuals, review activities | `CandidateShape`, lifecycle queries, review APIs | Reuse |
| Candidate source/provenance | `prov:wasDerivedFrom`, `prov:wasGeneratedBy`, `prov:generatedAtTime`, `prov:used`, `prov:generated` | `CandidateShape`, provenance/isolation checks | Reuse |
| Generator and ontology version | `projecta:generator`, `projecta:proposedOntologyVersion` | `CandidateShape`, CQ-EV-003 | Reuse with narrower gateway mapping |
| Entity candidate type/label/value | Generic `Candidate` and released knowledge classes exist, but no approved M3 payload shape binds a proposed entity mention/label to an allowlisted type | Existing CandidateShape validates lifecycle/provenance, not typed extraction payload | Gap: contract/shape decision required; likely additive semantic design |
| Relation candidate | No released relation-candidate class, source/target/predicate/evidence contract, or shape | Existing ontology has domain relation vocabulary but no untrusted relation proposal representation | Gap: S5-05 governed proposal required |
| Entity-link proposal | Project scope and identity concepts exist, but no candidate-link class/target/evidence/confidence semantics | Isolation checks detect cross-project references but do not model bounded link proposals | Gap: S5-05 governed proposal required |
| Confidence | No released candidate confidence property; confidence is not truth or review state | Candidate lifecycle and trust model deliberately separate suggestion from assertion | Gap or operational-only decision; requires explicit semantic commitment |
| Model/prompt/schema/usage metadata | `prov:Activity`, timestamps, and `generator` provide a provenance anchor; exact version/usage fields do not exist | Provenance queries cover activity and generator, not prompt/schema/usage | Gap for durable audit fields; telemetry-only fields may remain operational |
| Abstention/error/retry telemetry | No released domain term; error taxonomy classifies safe operational events | No ontology shape/query for provider attempts or redacted errors | Reuse boundary: keep operational unless a governance CQ requires RDF truth |

## Conclusions

The released v0.3 contract fully covers source immutability, exact evidence,
project isolation, candidate lifecycle, human review, baseline provenance,
generator identity, ontology version, graph routing, and rollback boundaries.

S5-05 is required for three semantic gaps: rich typed entity-candidate
payloads, relation candidates, and bounded entity-link proposals. Confidence
and extraction configuration metadata need a commitment decision. Provider
retry, latency, token usage, and error telemetry should remain operational by
default; they become ontology changes only if a reviewed competency question
requires durable cross-system semantic queryability.

No released IRI, shape, query, fixture, or migration is changed by S5-04.
Existing v0.1–v0.3 compatibility remains intact.

## Governance Review Packet

- **Business/use-case need:** Answer the twelve M3 questions without allowing untrusted model output to become asserted knowledge.
- **Reuse decision:** Preserve all released source, evidence, lifecycle, provenance, project, and graph contracts.
- **Required proposal:** Model the smallest reviewable representation for entity, relation, and bounded link candidates; decide whether confidence and version metadata are semantic or operational.
- **Alternatives:** Keep rich proposals only as opaque application payloads (fails graph/evidence/review CQs); overload `Candidate` literals (loses relation/link identity and validation); add narrowly scoped proposal terms (preferred for durable M3 graph queries).
- **Status:** `REVIEWED_AND_APPROVED`; S5-05 produced the governed proposal and review evidence, and the dependent v0.4 semantic artifacts are approved.
