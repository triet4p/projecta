# Namespace Policy — Proposal for Sprint 1

**Status:** APPROVED (2026-07-28)
**Decision record:** [.agents/memory/decisions.md](../../.agents/memory/decisions.md#2026-07-28-adopt-w3idorg-projecta-base-iri-and-naming-conventions)

## 1. Purpose

This document proposes the base IRI, prefix declarations, naming conventions, and ontology-version IRI structure for the Projecta ontology kernel (Sprint 1). Once approved, this policy governs all Turtle/TriG files, SHACL shapes, SPARQL queries, and ontology metadata produced in Sprint 1 and beyond.

## 2. Base IRI

**Proposal:** `https://w3id.org/projecta/ontology/`

### Rationale

- **`w3id.org`** is the W3C Permanent Identifier Community Group service — widely used by open-source ontologies (e.g., DBpedia, ODRL, DCAT) for persistent, redirectable URIs without requiring domain ownership.
- **`projecta`** matches the product name, is recognizable, and is unlikely to collide with other registrations.
- **`/ontology/`** separates the vocabulary namespace from instance data (`/data/`) and documentation.

### Alternatives considered

| Option | Verdict |
|---|---|
| `https://purl.org/projecta/ontology/` | Viable; purl.org is also well-established. `w3id.org` chosen for stronger W3C community governance. |
| `http://projecta.dev/ontology/` | Rejected — no domain ownership; `projecta.dev` is not registered. |
| `https://github.com/<user>/projecta/ontology/` | Rejected — ties the namespace to a specific hosting platform and account. |

## 3. Prefix Declarations

### 3.1. Project prefix

**Proposal:** `projecta:` → `https://w3id.org/projecta/ontology/`

All Sprint 1 ontology terms (classes, object properties, datatype properties) use this single prefix. Module-specific sub-namespaces (e.g., `comm:`, `work:`) are deferred until the modularization step in Sprint 2+.

### 3.2. Standard prefix set

Every Turtle/TriG file in Sprint 1 must declare:

```turtle
@prefix projecta: <https://w3id.org/projecta/ontology/> .
@prefix rdf:      <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:     <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:      <http://www.w3.org/2002/07/owl#> .
@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .
@prefix sh:       <http://www.w3.org/ns/shacl#> .
@prefix prov:     <http://www.w3.org/ns/prov#> .
```

Additional prefixes may be added per file as needed (e.g., `dcterms:` for Dublin Core metadata on the ontology itself).

### 3.3. Instance data prefix

**Proposal:** `projecta-data:` → `https://w3id.org/projecta/data/`

Separates vocabulary terms from instance data. Project-scoped instances follow the pattern:

```text
https://w3id.org/projecta/data/project/{project-id}/{entity-type}/{local-id}
```

Examples:

- `https://w3id.org/projecta/data/project/ecommerce-checkout/note/sprint-review-2026-07-28`
- `https://w3id.org/projecta/data/project/ecommerce-checkout/person/le`

## 4. Naming Conventions

### 4.1. Classes

**Convention:** PascalCase

| Term | Rationale |
|---|---|
| `projecta:Note` | Matches class name in the ontology design hierarchy |
| `projecta:NoteItem` | PascalCase, two words |
| `projecta:SourceArtifact` | PascalCase, two words |
| `projecta:Project` | Single word |
| `projecta:Person` | Single word |

Prefer single-word class names where unambiguous (`Note`, `Project`, `Person`). Use compound PascalCase when needed (`NoteItem`, `SourceArtifact`).

### 4.2. Object properties

**Convention:** camelCase, verb-phrase or prepositional phrase

| Term | Meaning |
|---|---|
| `projecta:belongsToProject` | Note → Project |
| `projecta:hasNoteItem` | Note → NoteItem |
| `projecta:authoredBy` | Note → Person |
| `projecta:hasMember` | Project/Team → Person |

- Use present-tense verb forms (`implements`, not `implementedBy` — provide the inverse via `owl:inverseOf`).
- Start with a verb or preposition (`belongsTo`, `has`, `authoredBy`, `derivedFrom`).

### 4.3. Datatype properties

**Convention:** camelCase, noun-phrase

| Term | Type |
|---|---|
| `projecta:contentText` | xsd:string |
| `projecta:recordedAt` | xsd:dateTime |
| `projecta:title` | xsd:string |

### 4.4. Named individuals (ontology-level)

**Convention:** kebab-case, descriptive

| Individual | Purpose |
|---|---|
| `projecta:requirement` | NoteItem type — a requirement capture |
| `projecta:decision` | NoteItem type — a decision capture |
| `projecta:risk` | NoteItem type — a risk capture |

These are the controlled vocabulary individuals for `NoteItem` types. They live in the ontology namespace (not the data namespace) because they define the vocabulary, not instance data.

### 4.5. SHACL shapes

**Convention:** `<ClassName>Shape`

| Shape | Target |
|---|---|
| `projecta:NoteShape` | `projecta:Note` |
| `projecta:NoteItemShape` | `projecta:NoteItem` |

### 4.6. Inference rules

**Convention:** kebab-case identifier

Rules are identified by a stable string, not an IRI in Sprint 1:

| Rule ID | Description |
|---|---|
| `delivery-risk` | Blocked task → requirement at risk |
| `impact-review` | Superseded requirement → tasks need review |

Rule IRIs may be introduced in Sprint 2 if the rule engine requires them.

### 4.7. What about `UPPER_SNAKE` in existing docs?

The [Ontology Design](../initialization/05-Ontology-Design.md) §5 lists conceptual properties in UPPER_SNAKE (`BELONGS_TO_PROJECT`, `IMPLEMENTS`, `BLOCKS`). This was a listing convention for readability, not a final IRI form. All properties in actual Turtle files must use camelCase per this policy.

## 5. Ontology Version Convention

### 5.1. Version IRI pattern

```text
https://w3id.org/projecta/ontology/v/{MAJOR}.{MINOR}/
```

| Version | IRI | Sprint |
|---|---|---|
| `0.1` | `https://w3id.org/projecta/ontology/v/0.1/` | Sprint 1 |
| `0.2` | `https://w3id.org/projecta/ontology/v/0.2/` | Sprint 2 |
| `1.0` | `https://w3id.org/projecta/ontology/v/1.0/` | First stable |

- **MAJOR (`0`→`1`):** Breaking changes — class removal, property domain/range change, SHACL shape that invalidates previously valid data.
- **MINOR (`1`→`2`):** Additive changes — new classes, new properties, new shapes that don't invalidate existing data.
- **PATCH (`0.1.0`→`0.1.1`):** Non-semantic changes — label fixes, documentation-only, comment updates. PATCH is recorded in `owl:versionInfo` but does not get its own version IRI.

### 5.2. Development IRI

```text
https://w3id.org/projecta/ontology/dev/
```

The `dev/` IRI is the working copy used during active development. It is mutable. A versioned IRI is an immutable release snapshot.

### 5.3. Ontology metadata

Every Turtle module must include at minimum:

```turtle
<https://w3id.org/projecta/ontology/v/0.1/>
    a owl:Ontology ;
    owl:versionIRI <https://w3id.org/projecta/ontology/v/0.1/> ;
    owl:versionInfo "0.1.0" ;
    rdfs:label "Projecta Ontology — Sprint 1 Kernel" ;
    dcterms:created "2026-07-28"^^xsd:date ;
    dcterms:creator "Projecta contributors" .
```

## 6. Named Graph IRIs

For Sprint 1, the named graph model (from [Ontology Design §8](../initialization/05-Ontology-Design.md#8-named-graph-model)) is expressed as:

```text
https://w3id.org/projecta/ontology/v/0.1/              # ontology graph (vocabulary)
https://w3id.org/projecta/ontology/v/0.1/shapes/        # SHACL shapes
https://w3id.org/projecta/ontology/v/0.1/rules/         # inference rules

https://w3id.org/projecta/data/project/{id}/sources/    # source artifact metadata
https://w3id.org/projecta/data/project/{id}/candidates/ # unconfirmed candidates
https://w3id.org/projecta/data/project/{id}/asserted/   # human-confirmed facts
https://w3id.org/projecta/data/project/{id}/inferred/   # reasoner output
https://w3id.org/projecta/data/project/{id}/provenance/ # activity and derivation records
```

## 7. Migration Path

The [Ontology Design](../initialization/05-Ontology-Design.md) examples use `brse:` as an illustrative prefix. This was a placeholder — no Turtle files exist yet. The `brse:` prefix is superseded by `projecta:` in all future artifacts.

## 8. Sprint 1 Scope

For Sprint 1, only the following namespaces are populated:

| Namespace | Contents |
|---|---|
| `https://w3id.org/projecta/ontology/v/0.1/` | Core vocabulary: Note, NoteItem, Project, Person, properties |
| `https://w3id.org/projecta/data/project/ecommerce-checkout/` | Demo graph instances (S1-10) |

Module sub-namespaces, SHACL shapes, and rules are created in later sprint tasks (S1-08, S1-09) but remain in the base namespace for Sprint 1.

## 9. Acceptance Criteria

- [x] Base IRI proposed with rationale and alternatives considered.
- [x] Prefix `projecta:` and standard prefix set declared.
- [x] Naming conventions defined for classes, object properties, datatype properties, individuals, SHACL shapes, and rules.
- [x] Version IRI pattern defined with dev/production distinction.
- [x] Named graph IRI structure aligned with the ontology design document.
- [x] Migration note for existing `brse:` placeholder prefix.
- [x] Human reviewer approves the namespace policy (→ S1-05 `$log-decision`).
