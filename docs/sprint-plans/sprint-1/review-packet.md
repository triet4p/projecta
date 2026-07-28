# Sprint 1 Review Packet — Ontology Kernel v0.1

**Status:** IMPLEMENTED_PENDING_RELEASE_APPROVAL
**Date:** 2026-07-28
**Version:** 0.1.0
**Human decision:** Approved for the repository-local v0.1 release on
2026-07-28. Public IRI publication remains gated on w3id.org registration.

## Semantic Outcome

Sprint 1 delivers a minimum ontology kernel supporting the Quick Note vertical slice. The kernel defines 9 classes, 6 object properties (4 primary + 2 inverses), 3 datatype properties, and 9 controlled vocabulary individuals — sufficient to capture a typed, project-scoped note with author provenance and to answer 14 competency questions via SPARQL. No SHACL shapes, inference rules, candidate extraction, or connector terms are included.

## Justification

- **Use case:** Quick Note capture by BrSE ([docs/use-cases/quick-note.md](../../use-cases/quick-note.md))
- **Competency questions:** 14 questions approved in S1-03, implemented and validated in S1-11
- **Governance:** Terms follow the namespace policy (S1-04/S1-05), semantic commitment interviews (S1-06/S1-07), and the `projecta-evolve-ontology` workflow
- **Architecture alignment:** Class hierarchy matches Ontology Design §4; named graph model matches §8; PROV-O alignment per S1-07 decision

## Proposed Design

### Classes (9)

| Class | Superclass | Module |
|---|---|---|
| `projecta:Entity` | — | core |
| `projecta:Context` | Entity | core |
| `projecta:Project` | Context | core |
| `projecta:Actor` | Entity | core |
| `projecta:Person` | Actor | core |
| `projecta:SourceArtifact` | Entity | core |
| `projecta:Note` | SourceArtifact | communication |
| `projecta:NoteItem` | Entity | communication |
| `projecta:NoteItemType` | Entity | communication |

### Object Properties (6: 4 primary + 2 inverses)

| Property | Domain | Range | Notes |
|---|---|---|---|
| `projecta:belongsToProject` | Entity | Project | Broad domain; SHACL constrains in Sprint 2 |
| `projecta:hasNoteItem` | Note | NoteItem | |
| `projecta:isItemOf` | — | — | `owl:inverseOf hasNoteItem` |
| `projecta:authoredBy` | SourceArtifact | Person | `rdfs:subPropertyOf prov:wasAttributedTo` |
| `projecta:authorOf` | — | — | `owl:inverseOf authoredBy` |
| `projecta:hasItemType` | NoteItem | NoteItemType | |

### Datatype Properties (3)

| Property | Domain | Range |
|---|---|---|
| `projecta:name` | Entity | xsd:string |
| `projecta:contentText` | NoteItem | xsd:string |
| `projecta:recordedAt` | SourceArtifact | xsd:dateTime; subproperty of `prov:generatedAtTime` |

### Controlled Individuals (9)

All instances of `projecta:NoteItemType`: `requirement`, `decision`, `question`,
`task`, `risk`, `assumption`, `constraint`, `progress-update`, and
`research-need`.

## Artifact Diff

### Semantic and validation artifacts

**Ontology source (vocabulary):**
- `ontology/core.ttl` — 43 triples: foundation classes + `belongsToProject`, `name`
- `ontology/communication.ttl` — 76 triples: Quick Note vocabulary, properties, inverses, controlled individuals
- `infra/docker/fuseki/config/location-mapping.ttl` — Jena offline IRI resolution mapping

**Ontology source (examples/fixtures):**
- `ontology/examples/quick-note-demo.trig` — 33 triples: positive example (BrSE Le, 6-item note)
- `ontology/examples/negative-orphan-noteitem.trig` — orphan NoteItem fixture
- `ontology/examples/negative-missing-project.trig` — missing project fixture
- `ontology/examples/negative-invalid-itemtype.trig` — invalid hasItemType fixture

**Competency questions and queries:**
- `ontology/competency-questions/quick-note.md` — 14 CQ specifications
- `ontology/competency-questions/quick-note-queries.rq` — 14 SPARQL queries
- `ontology/competency-questions/negative-queries.rq` — 3 data-quality ASK queries
- `scripts/validate_ontology.py` — Complete container-side validation suite

**Docker and test infrastructure:**
- `infra/docker/fuseki/Dockerfile` — Jena 6.1.0 + Fuseki + Python3/rdflib
- `compose.yaml` — canonical Jena service definition
- `compose.dev.yaml` — local Jena port override
- `compose.yaml` service `ontology-test` — Cross-platform disposable test entry point

### Documentation

- `docs/use-cases/quick-note.md` — Quick Note use case boundary (S1-01)
- `docs/ontology/namespace-policy.md` — Base IRI, prefixes, naming, versioning (S1-04)
- `docs/ontology/term-inventory-sprint-1.md` — 20-term inventory with semantic commitment interviews (S1-06)
- `docs/sprint-plans/sprint-1/review-packet.md` — This document (S1-14)
- `docs/sprint-plans/sprint-1.md` — Sprint plan with status tracking
- `docs/sprint-plans/sprint-1/artifacts/task_S1-*_summary.md` — implementation task summaries

### Decisions and lessons

- `.agents/memory/decisions.md` — Namespace, Jena image, canonical layout, and Docker-native test entry point
- `.agents/memory/lessons-learned.md` — Docker, compact IRI, TriG, pip compatibility, layout, and host-shell findings

## Validation Evidence

### Automated checks — PASSED

Canonical command:

```text
docker compose run --build --rm ontology-test
```

| Check | Tool | Result |
|---|---|---|
| RDF syntax | Jena `riot --validate` | 6/6 ontology and fixture files pass |
| Vocabulary counts | rdflib assertions | 4/4 exact inventory counts pass |
| Competency query inventory | Runner guard | Exactly 14 approved CQs found |
| Competency results | SPARQL SELECT/ASK | 14/14 exact row/boolean expectations pass |
| Negative query inventory | Runner guard | Exactly 3 approved detectors found |
| Negative detection | SPARQL ASK | 3/3 false on clean data and true on matching bad fixture |

**Overall result:** 32/32 checks passed on 2026-07-28.

### Checks not run (tooling or artifacts absent)

| Check | Reason |
|---|---|
| OWL consistency / profile check | No OWL reasoner configured — out of Sprint 1 scope |
| SHACL conformance | SHACL shapes not yet created (Sprint 2) |
| Jena rule execution | No inference rules defined (Sprint 2) |
| Full Jena SPARQL regression | TriG named-graph handling in Jena `sparql` CLI requires TDB2 loading or query modification; rdflib used as primary engine |
| CI pipeline execution | No CI configuration exists yet |

### Manual semantic inspection — COMPLETED

- Human review of Quick Note use case boundary (S1-01 → approved S1-03)
- Human review of 14 competency questions (S1-02 → approved S1-03)
- Human review of namespace policy (S1-04 → approved S1-05)
- Human review of 20-term semantic commitments (S1-06 → approved S1-07)

## Compatibility and Risk

| Consumer | Impact | Status |
|---|---|---|
| Ontology modules | No existing modules — greenfield | — |
| SHACL shapes | Not yet created — no regression risk | Sprint 2 |
| Inference rules | Not yet created — no regression risk | Sprint 2 |
| SPARQL queries | 14 CQs defined and tested — baseline established | Stable |
| Existing RDF data | None — greenfield | — |
| Demo graph | 1 positive + 3 negative fixtures — all valid under current vocabulary | Stable |
| Semantic Core code | No code yet — greenfield | — |
| Python contracts | No code yet — greenfield | — |
| Connectors | None — manual Quick Note only | Sprint 3+ |
| Docker infrastructure | `projecta-jena:6.1.0`, `compose.yaml`, `ontology-test` service | Stable |
| Permissions / authorization | Project scoping modeled at vocabulary level; no auth implementation | Deferred |

### Known risks

1. **Module namespace separation deferred:** All terms use single `projecta:` prefix. When Sprint 2 adds module sub-namespaces (`core:`, `comm:`, etc.), existing IRIs may need `owl:equivalentClass` mappings. Mitigation: the namespace policy §3.1 explicitly defers module prefixes.

2. **No SHACL shapes:** Application-level constraints (cardinality, required fields) are enforced only by SPARQL data-quality queries in Sprint 1. SHACL shapes in Sprint 2 will provide formal, machine-readable validation. The SPARQL queries serve as a stopgap and test oracle.

3. **TriG named-graph handling in Jena CLI:** Jena `sparql --data` does not merge TriG named graphs into the default graph. The validation script uses rdflib's `Dataset` API which handles this natively. Full Jena-based query testing will need TDB2 loading in Sprint 2.

## Deferred Questions

1. **NoteItem identity criterion (S1-06):** If NoteItems are auto-generated with
   UUID-based IRIs, deduplication on Note re-processing needs an identity
   strategy. Deferred to Sprint 2.

2. **Edit/delete semantics:** Note content is immutable in Sprint 1. Mutation
   flows are deferred to Sprint 3+.

## Human Actions Requested

- [x] Approve semantic meaning of the Sprint 1 Quick Note kernel.
- [x] Approve vocabulary names and stable
  `https://w3id.org/projecta/ontology/` IRIs.
- [x] Approve the current SPARQL validation behavior; SHACL remains Sprint 2.
- [x] Confirm inference behavior is intentionally absent until Sprint 2.
- [x] Confirm no migration/deprecation artifact is required for this greenfield
  release.
- [x] Confirm Apache 2.0 is the ontology license.
- [x] Defer w3id.org registration until before the first public release.
- [x] Use kebab-case controlled-individual IRIs.
- [x] Authorize repository-local ontology v0.1 release and completion of S1-15.
