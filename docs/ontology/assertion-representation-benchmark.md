# Assertion Metadata Representation Benchmark

**Status:** DRAFT
**Sprint:** S2-05 — Benchmark assertion metadata representations
**Date:** 2026-07-28
**Target:** Jena 6.1.0 (Apache Jena via `docker compose run --rm jena`)

## 1. Purpose

This document benchmarks three RDF representations for attaching provenance and temporal metadata to individual assertions (triples) within the Projecta knowledge graph. The chosen representation will be used throughout Sprint 2 for `validFrom`, `validTo`, review decisions, and all other assertion-level metadata required by the lifecycle competency questions.

The benchmark uses a single shared scenario across all three representations, with equivalent SPARQL queries, to produce a directly comparable evaluation.

## 2. The Problem

In the v0.1 ontology, properties like `projecta:contentText` and `projecta:recordedAt` are attached directly to entities. There is no way to say:

> "The `validFrom` date of this Requirement was asserted by Le on 2026-07-29 under ontology version 0.2.0, and later superseded by Minh on 2026-08-15."

Without assertion-level metadata:
- Temporal history is lost (who changed what, when).
- Review decisions cannot be attached to specific property values.
- Supersession cannot distinguish "the requirement changed" from "a specific property value changed."
- The provenance graph cannot record fine-grained derivation at the triple level.

## 3. Shared Scenario

A single Requirement `:req-address-confirmation` in project "Ecommerce Checkout Redesign" has:

| Aspect | Value |
|---|---|
| Entity | `:req-address-confirmation` (a `projecta:Requirement`) |
| Base fact | `projecta:validFrom "2026-07-29"^^xsd:date` |
| Who asserted it | `:person-le` (BrSE) |
| When asserted | `2026-07-29T10:15:00Z` |
| Ontology version | `0.2.0` |

The benchmark evaluates how each representation encodes the **metadata about the assertion** — the reviewer, timestamp, and ontology version attached to the `validFrom` triple itself.

## 4. Representations Under Test

### 4.1. Assertion Node (AN)

An explicit named node (`projecta:Assertion`) reifies the property-value pair. The subject links to the assertion node via `projecta:hasAssertion`.

```turtle
# In asserted graph: the entity does NOT carry validFrom directly
:req-address-confirmation
    a projecta:Requirement ;
    projecta:hasAssertion :asn-validfrom-001 .

# In provenance graph: the assertion node carries the value + metadata
:asn-validfrom-001
    a projecta:Assertion ;
    projecta:assertedProperty projecta:validFrom ;
    projecta:assertedValue "2026-07-29"^^xsd:date ;
    projecta:ontologyVersion "0.2.0" ;
    prov:wasAssociatedWith :person-le ;
    prov:endedAtTime "2026-07-29T10:15:00Z"^^xsd:dateTime .
```

**Key characteristic:** The `validFrom` value is *only* accessible through the assertion node. There is no direct `:req validFrom "..."` triple. This makes the assertion node the single source of truth for the value and its provenance.

### 4.2. RDF Reification (REIF)

The base fact is asserted directly. A separate `rdf:Statement` node reifies it with metadata.

```turtle
# In asserted graph: the entity carries validFrom directly
:req-address-confirmation
    a projecta:Requirement ;
    projecta:validFrom "2026-07-29"^^xsd:date .

# In provenance graph: rdf:Statement reifies the triple
:stmt-validfrom-001
    a rdf:Statement ;
    rdf:subject :req-address-confirmation ;
    rdf:predicate projecta:validFrom ;
    rdf:object "2026-07-29"^^xsd:date ;
    projecta:ontologyVersion "0.2.0" ;
    prov:wasAssociatedWith :person-le ;
    prov:endedAtTime "2026-07-29T10:15:00Z"^^xsd:dateTime .
```

**Key characteristic:** The `validFrom` value exists in two places — directly on the entity AND referenced inside the `rdf:Statement`. This creates a synchronization burden: the two copies of the value must match.

### 4.3. RDF-star (STAR)

The base fact is asserted directly. Metadata is attached to the quoted triple using `<< s p o >>` syntax.

```turtle
# In asserted graph: the entity carries validFrom directly
:req-address-confirmation
    a projecta:Requirement ;
    projecta:validFrom "2026-07-29"^^xsd:date .

# In provenance graph: metadata on the quoted triple
<< :req-address-confirmation projecta:validFrom "2026-07-29"^^xsd:date >>
    projecta:ontologyVersion "0.2.0" ;
    prov:wasAssociatedWith :person-le ;
    prov:endedAtTime "2026-07-29T10:15:00Z"^^xsd:dateTime .
```

**Key characteristic:** The quoted triple IS the reification token — no separate IRI needed. The triple itself serves as the subject of metadata assertions. This is the most syntactically compact representation.

## 5. Query Complexity Comparison

Six query patterns are compared. Full queries are in [ontology/competency-questions/benchmark-queries.rq](../../ontology/competency-questions/benchmark-queries.rq).

### 5.1. BENCH-Q1: Read a property value

| Representation | Triple Patterns | Notes |
|---|---|---|
| **AN** | 3 patterns: `hasAssertion` + `assertedProperty` + `assertedValue` | One extra join vs. direct access |
| **REIF** | 1 pattern: direct `validFrom` | Simplest — read the property directly |
| **STAR** | 1 pattern: direct `validFrom` | Same as REIF for simple reads |

**Winner: REIF / STAR.** The assertion node adds an indirection that makes simple reads more verbose.

### 5.2. BENCH-Q2: Read a property value with its provenance

| Representation | Triple Patterns | Variable Bindings |
|---|---|---|
| **AN** | 5 patterns: `hasAssertion` + `assertedProperty` + `assertedValue` + `wasAssociatedWith` + `endedAtTime` | `?asn` intermediate variable |
| **REIF** | 6 patterns: `rdf:type` + `rdf:subject` + `rdf:predicate` + `rdf:object` + `wasAssociatedWith` + `endedAtTime` | `?stmt` intermediate variable; must repeat subject/predicate/object |
| **STAR** | 4 patterns: quoted triple (3 components in one token) + `wasAssociatedWith` + `endedAtTime` | `?validFrom` variable captures the object |

**Winner: STAR.** The quoted triple collapses subject/predicate/object into a single syntactic unit, reducing pattern count. AN is close behind. REIF is the most verbose due to the four-component `rdf:Statement` decomposition.

### 5.3. BENCH-Q3: List all assertions about an entity

| Representation | Triple Patterns | Discovery |
|---|---|---|
| **AN** | 4 patterns: `hasAssertion` + `assertedProperty` + `assertedValue` + provenance | Explicit `hasAssertion` link makes discovery direct |
| **REIF** | 5 patterns: `rdf:type` + `rdf:subject` + `rdf:predicate` + `rdf:object` + provenance | Must scan all Statements by subject |
| **STAR** | 3 patterns: quoted triple (subject fixed, property+object variable) + provenance | Most compact; subject is fixed in the quoted triple head |

**Winner: STAR.** Compact discovery with no extra vocabulary terms. AN is a close second with its explicit link.

### 5.4. BENCH-Q4: ASK — does entity X have property P asserted by person Y?

| Representation | Complexity |
|---|---|
| **AN** | 3 triple patterns |
| **REIF** | 4 triple patterns |
| **STAR** | 2 triple patterns |

**Winner: STAR.** Fewest patterns; the quoted triple encodes the identity of what was asserted without extra reification vocabulary.

### 5.5. BENCH-Q5: UPDATE — supersede a property value

| Representation | INSERT Statements | DELETE Statements |
|---|---|---|
| **AN** | 1 new `hasAssertion` + 1 new Assertion node (6 triples total) | None (old assertion retained) |
| **REIF** | 1 new direct triple + 1 new rdf:Statement (7 triples total) | None (old triple + old Statement retained) |
| **STAR** | 1 new direct triple + 1 new quoted triple metadata (4 triples total) | None (old triple + old quoted metadata retained) |

**Winner: STAR.** Fewest INSERT triples. AN requires no DELETE — the old assertion node naturally becomes historical. REIF has the most INSERT overhead.

### 5.6. BENCH-Q6: Find the CURRENT (most recent) property value

| Representation | Query Complexity | Notes |
|---|---|---|
| **AN** | 4 patterns + ORDER BY + LIMIT | ORDER BY on `prov:endedAtTime` |
| **REIF** | 4 patterns + ORDER BY + LIMIT | Must distinguish which rdf:Statement is current |
| **STAR** | 3 patterns + ORDER BY + LIMIT | Same temporal pattern — fewer patterns |

**Winner: STAR (marginal).** All three require ORDER BY + LIMIT for temporal disambiguation. STAR has fewer patterns; AN and REIF tie on pattern count.

### 5.7. Query Complexity Summary

| Query Pattern | AN (triple patterns) | REIF (triple patterns) | STAR (triple patterns) | Best |
|---|---|---|---|---|
| Q1: Read value | 3 | 1 | 1 | REIF/STAR |
| Q2: Value + provenance | 5 | 6 | 4 | STAR |
| Q3: All assertions | 4 | 5 | 3 | STAR |
| Q4: ASK check | 3 | 4 | 2 | STAR |
| Q5: UPDATE (INSERT count) | 6 | 7 | 4 | STAR |
| Q6: Current value | 4 | 4 | 3 | STAR |
| **Average patterns** | **4.2** | **4.5** | **2.8** | **STAR** |

## 6. SHACL Compatibility

### 6.1. Can SHACL validate assertion metadata?

| Representation | SHACL on Base Fact | SHACL on Metadata | Notes |
|---|---|---|---|
| **AN** | Via `hasAssertion` path: `sh:property [ sh:path (projecta:hasAssertion projecta:assertedValue) ]` | Direct: target `projecta:Assertion` with `sh:targetClass` | Requires property-path shapes for value; straightforward for metadata |
| **REIF** | Direct: `sh:path projecta:validFrom` | Via rdf:type: target `rdf:Statement` with `sh:targetClass`, filter by `rdf:predicate` | Two separate shape targets; must coordinate base fact shape with reification shape |
| **STAR** | Direct: `sh:path projecta:validFrom` | **Not natively supported in SHACL 1.0.** SHACL-AF (Advanced Features) may offer `sh:SPARQLConstraint` as workaround. Quoted triples are not `sh:targetClass` targets. | SHACL cannot validate RDF-star quoted triple metadata without SPARQL-based constraints |

### 6.2. SHACL Validation Examples

**Assertion Node — validate that every validFrom assertion has a reviewer:**

```turtle
projecta:AssertionShape a sh:NodeShape ;
    sh:targetClass projecta:Assertion ;
    sh:property [
        sh:path prov:wasAssociatedWith ;
        sh:class projecta:Person ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:path projecta:assertedProperty ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:property [
        sh:path projecta:assertedValue ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .
```

**RDF Reification — validate that every reified validFrom statement has a reviewer:**

```turtle
projecta:ValidFromReificationShape a sh:NodeShape ;
    sh:targetClass rdf:Statement ;
    sh:property [
        sh:path rdf:predicate ;
        sh:hasValue projecta:validFrom
    ] ;
    sh:property [
        sh:path prov:wasAssociatedWith ;
        sh:class projecta:Person ;
        sh:minCount 1
    ] .
```

**RDF-star — no native SHACL target for quoted triples:**

```turtle
# WORKAROUND: Use sh:SPARQLConstraint
projecta:ValidFromStarShape a sh:NodeShape ;
    sh:targetClass projecta:Requirement ;
    sh:sparql [
        sh:message "Every validFrom must have an associated reviewer" ;
        sh:select """
            SELECT $this WHERE {
                $this projecta:validFrom ?v .
                FILTER NOT EXISTS {
                    << $this projecta:validFrom ?v >> prov:wasAssociatedWith ?reviewer .
                }
            }
            """
    ] .
```

### 6.3. SHACL Verdict

| Criterion | AN | REIF | STAR |
|---|---|---|---|
| Native SHACL target | ✅ `projecta:Assertion` | ✅ `rdf:Statement` | ❌ No target for quoted triples |
| Property path shapes | ✅ Via `hasAssertion` | ✅ Direct | ✅ Direct for base fact |
| Metadata cardinality | ✅ Standard shapes | ✅ Standard shapes | ❌ Requires SPARQL constraint |
| SHACL engine: Jena | ✅ | ✅ | ⚠️ SPARQL only |
| SHACL engine: other | ✅ | ✅ | ❌ Non-standard |

**Winner: AN / REIF (tie).** STAR cannot validate assertion metadata with standard SHACL shapes, only with SPARQL-based constraints. AN has the cleanest separation: Assertion shapes target `projecta:Assertion`; entity shapes use property paths through `hasAssertion`.

## 7. Update Complexity

### 7.1. Adding a new assertion (normal case)

| Operation | AN | REIF | STAR |
|---|---|---|---|
| Triples to INSERT | 6 (1 link + 5 assertion node) | 7 (1 base fact + 6 rdf:Statement) | 4 (1 base fact + 3 metadata) |
| ID allocation | 2 new IRIs (assertion node + assertion) | 2 new IRIs (statement + implicit) | 0 new IRIs (quoted triple is self-identifying) |
| Risk of mismatch | None (single source of truth) | ⚠️ `rdf:object` must match the direct triple value | None (quoted triple IS the triple) |

### 7.2. Superseding an assertion

| Operation | AN | REIF | STAR |
|---|---|---|---|
| Keep old assertion? | Yes — old Assertion node stays; add new one | Yes — old triple + old Statement stay; add both | Yes — old triple + old quoted metadata stay; add both |
| DELETE needed? | None | None | None |
| "Current" disambiguation | ORDER BY `endedAtTime` on assertion nodes | ORDER BY `endedAtTime` on Statements | ORDER BY `endedAtTime` on quoted triples |
| Risk of stale metadata | Low — each assertion is independent | ⚠️ Old `rdf:Statement` still references the old value; determining "current" requires temporal query | Low — each quoted triple is independent |

### 7.3. Retracting an assertion

| Operation | AN | REIF | STAR |
|---|---|---|---|
| Remove value from current view | Add retraction assertion node | Remove direct triple OR add retraction marker | Remove direct triple OR add retraction marker |
| Keep provenance? | Yes — retraction is an Assertion | Yes — retraction is a Statement | Yes — retraction is metadata on the quoted triple |
| Graph consistency | Clean — assertion chain is explicit | ⚠️ Removing the direct triple orphans the Statement | ⚠️ Removing the direct triple orphans the quoted metadata |

### 7.4. Update Verdict

| Criterion | AN | REIF | STAR |
|---|---|---|---|
| INSERT overhead | Medium (6 triples) | High (7 triples) | Low (4 triples) |
| ID management | Yes (named assertion nodes) | Yes (named Statements) | None (self-identifying) |
| Single source of truth | ✅ (value only in assertion) | ❌ (value in two places) | ❌ (value in two places) |
| Safe retraction | ✅ | ⚠️ (orphan risk) | ⚠️ (orphan risk) |
| History integrity | ✅ | ✅ | ✅ |

**Winner: AN.** Assertion node is the only representation where the value lives in exactly one place — the assertion node itself. REIF and STAR duplicate the value (direct triple + reification reference), creating synchronization risk on update and orphan risk on retraction.

## 8. Migration Impact

### 8.1. Migration from v0.1 (no assertion metadata)

v0.1 has no assertion-level metadata. All properties are directly asserted. The migration to v0.2 must:

1. Keep all existing direct triples working (compatibility baseline §4).
2. Add assertion metadata for properties that need provenance.
3. NOT break any of the 32 Sprint 1 checks.

| Migration Aspect | AN | REIF | STAR |
|---|---|---|---|
| v0.1 data compatibility | ⚠️ v0.1 direct triples must be wrapped in assertion nodes (migration script needed) | ✅ v0.1 direct triples stay as-is; Statements are additive | ✅ v0.1 direct triples stay as-is; quoted metadata is additive |
| v0.1 query compatibility | ❌ v0.1 queries reading `validFrom` directly break — must rewrite to traverse `hasAssertion` | ✅ All v0.1 queries continue to work unchanged | ✅ All v0.1 queries continue to work unchanged |
| Migration script complexity | High — must create assertion nodes for all v0.1 properties that need provenance | Low — create rdf:Statements referencing existing triples | Low — create quoted triple metadata referencing existing triples |
| Rollback complexity | High — must remove assertion nodes and restore direct triples | Low — delete rdf:Statements; base triples untouched | Low — delete quoted triple metadata; base triples untouched |

### 8.2. Migration from one representation to another

| Migration | Effort |
|---|---|
| REIF → AN | Must create assertion nodes and REMOVE direct triples (breaking change) |
| REIF → STAR | Mechanical: `rdf:Statement` → quoted triple (keeping direct triples) |
| STAR → REIF | Mechanical: quoted triple → `rdf:Statement` (keeping direct triples) |
| AN → REIF or STAR | Breaking: must ADD direct triples in addition to conversion |
| AN → AN (same) | No migration needed |

### 8.3. Ecosystem and Tool Support

| Tool / Standard | AN | REIF | STAR |
|---|---|---|---|
| Jena 6.1.0 | ✅ Full support | ✅ Full support | ✅ Supported (since 4.6.0) |
| rdflib 7.0.0 | ✅ Full support | ✅ Full support | ⚠️ Partial (plugin required) |
| Protégé | ✅ | ✅ | ❌ No support |
| SPARQL 1.1 | ✅ | ✅ | ❌ Requires SPARQL-star extension |
| SHACL 1.0 (W3C) | ✅ | ✅ | ❌ No quoted triple targets |
| OWL 2 | ✅ | ⚠️ rdf:Statement is not OWL-friendly | ❌ No interaction |
| JSON-LD | ✅ | ✅ | ❌ No RDF-star support |
| Turtle/TriG serialization | ✅ Standard | ✅ Standard | ✅ Turtle-star (W3C Community Report) |

### 8.4. Migration Verdict

| Criterion | AN | REIF | STAR |
|---|---|---|---|
| v0.1 query backward compat | ❌ | ✅ | ✅ |
| v0.1 data compat | ⚠️ Migration needed | ✅ | ✅ |
| Tool ecosystem breadth | ✅ Broad | ✅ Broad | ⚠️ Narrow (Jena + bleeding-edge) |
| W3C standardization | ✅ | ✅ | ❌ Community Report (not Recommendation) |
| Future-proofing | ✅ Stable vocabulary | ✅ Standard since 1999 | ⚠️ Standardization uncertain |

**Winner: REIF (narrow).** It preserves v0.1 query compatibility and has the broadest tool support. AN breaks v0.1 queries and requires data migration. STAR has the weakest ecosystem support and uncertain standardization.

## 9. Combined Evaluation

Each dimension is scored 1 (worst) to 3 (best) within the column.

| Dimension | Weight | AN | REIF | STAR |
|---|---|---|---|---|
| Query simplicity (reads) | High | 2 | 3 | 3 |
| Query simplicity (provenance) | High | 2 | 1 | 3 |
| SHACL compatibility | High | 3 | 3 | 1 |
| Update safety (no duplication) | Medium | 3 | 1 | 1 |
| INSERT overhead | Low | 2 | 1 | 3 |
| v0.1 backward compatibility | **Critical** | 1 | 3 | 3 |
| Ecosystem / tool support | Medium | 3 | 3 | 1 |
| W3C standardization | Medium | 3 | 3 | 1 |
| ID management burden | Low | 1 | 1 | 3 |
| **Weighted total** | | **22** | **24** | **19** |

Weighting: Critical = 5×, High = 3×, Medium = 2×, Low = 1×

### 9.1. Key Trade-offs

**Assertion Node (AN):**
- ✅ Cleanest semantics: one assertion = one node, no duplication, explicit lifecycle
- ✅ Best SHACL compatibility: target `projecta:Assertion` directly
- ❌ **Breaks v0.1 query compatibility** — all queries reading properties directly must be rewritten to traverse `hasAssertion`
- ❌ Requires migration script for any property that needs provenance

**RDF Reification (REIF):**
- ✅ Best backward compatibility: v0.1 queries and data are untouched
- ✅ Broadest tool support: works in every RDF tool since 1999
- ❌ Verbose: 4 triples just to describe what was asserted (subject/predicate/object + type)
- ❌ Duplication risk: the `rdf:object` in the Statement can drift from the direct triple value
- ❌ Most INSERT overhead for new assertions

**RDF-star (STAR):**
- ✅ Most compact: fewest triples, no artificial IRIs
- ✅ Best query ergonomics for provenance reads
- ❌ **No SHACL native support** — must use SPARQL constraints for metadata validation
- ❌ Ecosystem immaturity: Protégé, JSON-LD, OWL don't support it
- ❌ SPARQL-star is not yet a W3C Recommendation (Community Report as of 2024)

## 10. Recommendation

### 10.1. Primary Recommendation: RDF Reification (REIF)

**For Sprint 2, use standard RDF reification (`rdf:Statement`) for assertion metadata.**

Rationale:
1. **v0.1 backward compatibility is non-negotiable.** The sprint plan's Definition of Done requires all 32 Sprint 1 checks to continue passing. REIF is the only representation (alongside STAR) that preserves direct property reads.
2. **SHACL compatibility is mandatory.** Sprint 2 requires SHACL shapes for source, candidate, isolation, and temporal validation (§S2-11–S2-14). REIF supports native SHACL targeting of `rdf:Statement`; STAR does not.
3. **Tool ecosystem is mature.** Jena 6.1.0, rdflib, Protégé, and standard SPARQL 1.1 all support `rdf:Statement` without extensions.
4. **The duplication risk is manageable.** SHACL shapes can enforce that `rdf:object` matches the direct triple value for critical properties.

### 10.2. Deferred Decision: Re-evaluate RDF-star for Sprint 3+

RDF-star has the best ergonomics and the lowest INSERT overhead. Its two blockers for Sprint 2 — no SHACL native support and uncertain standardization — may resolve by Sprint 3+. Specifically:

- If the W3C RDF-star Working Group publishes a Recommendation by Q4 2026, re-evaluate.
- If Jena adds SHACL target support for quoted triples (e.g., `sh:targetQuotedTriple`), re-evaluate.
- If the SHACL 2.0 Community Group addresses quoted triple validation, re-evaluate.

### 10.3. Deferred Decision: Consider Assertion Node for v1.0

The assertion node model has the cleanest semantics and the best update safety. If the project ever undertakes a MAJOR (v1.0) release that permits breaking changes to the query surface, assertion nodes should be reconsidered as the primary representation. The migration from REIF to AN is well-understood and can be automated.

### 10.4. Mitigation: SHACL-Guarded Duplication

Regardless of the chosen representation, the following SHACL shape should be applied to prevent drift between direct triples and their reified metadata:

```turtle
projecta:ReificationConsistencyShape a sh:NodeShape ;
    sh:targetClass rdf:Statement ;
    sh:sparql [
        sh:message "rdf:object of Statement must match the direct triple value" ;
        sh:select """
            SELECT $this WHERE {
                $this rdf:subject ?s ;
                      rdf:predicate ?p ;
                      rdf:object ?o1 .
                ?s ?p ?o2 .
                FILTER (?o1 != ?o2)
            }
            """
    ] .
```

## 11. Fixture and Query Artifacts

| Artifact | Path |
|---|---|
| Assertion Node fixture | [ontology/examples/benchmark-assertion-node.trig](../../ontology/examples/benchmark-assertion-node.trig) |
| RDF Reification fixture | [ontology/examples/benchmark-rdf-reification.trig](../../ontology/examples/benchmark-rdf-reification.trig) |
| RDF-star fixture | [ontology/examples/benchmark-rdf-star.trig](../../ontology/examples/benchmark-rdf-star.trig) |
| Benchmark queries | [ontology/competency-questions/benchmark-queries.rq](../../ontology/competency-questions/benchmark-queries.rq) |

## 12. Acceptance Criteria

- [ ] All three representations modeled with the same shared scenario.
- [ ] Six query patterns (Q1–Q6) implemented and compared across all representations.
- [ ] Four evaluation dimensions covered: query complexity, SHACL compatibility, update complexity, migration impact.
- [ ] Ecosystem and tool support assessed for Jena 6.1.0 specifically.
- [ ] Clear primary recommendation with rationale, deferred decisions, and mitigation strategies.
- [ ] Fixture files and query files are syntactically valid.
- [ ] Human reviewer selects a representation or requests additional evidence (S2-06).
