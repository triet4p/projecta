# Task Summary: S2-05 — Benchmark Assertion Metadata Representations

**Sprint:** Sprint 2 — Governed Knowledge Lifecycle
**Task:** S2-05 — Benchmark Assertion Metadata Representations

## Summary of Work

Benchmarked three RDF representations for attaching provenance and temporal metadata to individual assertions, using a single shared scenario (an asserted Requirement with `validFrom` date, reviewer identity, timestamp, and ontology version). The three representations are:

- **Assertion Node (AN):** An explicit `projecta:Assertion` node reifies the property-value pair. The entity links to the assertion via `projecta:hasAssertion`. The value exists only in the assertion node — no direct triple on the entity. Single source of truth; 6 triples per assertion.
- **RDF Reification (REIF):** The base fact is asserted directly on the entity. A separate `rdf:Statement` node carries the metadata. The value exists in two places (direct triple + `rdf:object` in the Statement). Most compatible with existing tools; 7 triples per assertion.
- **RDF-star (STAR):** The base fact is asserted directly. Metadata is attached to the quoted triple using `<< s p o >>` syntax. Most compact; 4 triples per assertion; no artificial IRIs needed.

Created three TriG fixture files (one per representation), all passing Jena 6.1.0 `riot --validate`. Created a benchmark query file with 18 equivalent SPARQL queries (6 query patterns × 3 representations) covering: read value, read value with provenance, list all assertions, ASK check, UPDATE supersession, and find current value.

Evaluated across four dimensions:

1. **Query complexity:** STAR wins (2.8 average triple patterns vs. 4.2 for AN and 4.5 for REIF). However, STAR requires SPARQL-star extension syntax for provenance queries.
2. **SHACL compatibility:** AN/REIF tie — both support native `sh:targetClass` shapes. STAR cannot validate quoted triple metadata with standard SHACL and requires SPARQL-based constraints.
3. **Update complexity:** AN wins — the value lives in exactly one place (the assertion node), eliminating duplication risk on supersession/retraction. REIF and STAR duplicate the value (direct triple + reification reference).
4. **Migration impact:** REIF/STAR tie — v0.1 queries and data are preserved unchanged. AN breaks v0.1 query compatibility (all direct property reads must be rewritten to traverse `hasAssertion`).

Produced a combined weighted evaluation where REIF scores 24, AN scores 22, and STAR scores 19 (higher is better). The primary recommendation is **RDF Reification (REIF)** for Sprint 2, with RDF-star deferred for re-evaluation in Sprint 3+ (pending W3C standardization and SHACL working group progress) and Assertion Node deferred for consideration at v1.0 (when breaking query-surface changes are permitted).

## Files Modified

- [docs/ontology/assertion-representation-benchmark.md](../../../../docs/ontology/assertion-representation-benchmark.md) — New file: benchmark analysis with shared scenario, per-representation Turtle examples, 6-query comparison, 4-dimension evaluation, weighted scoring, recommendation with deferred decisions, and SHACL mitigation shape.
- [ontology/examples/benchmark-assertion-node.trig](../../../../ontology/examples/benchmark-assertion-node.trig) — New file: TriG fixture with assertion node representation (2 named graphs, 14 triples).
- [ontology/examples/benchmark-rdf-reification.trig](../../../../ontology/examples/benchmark-rdf-reification.trig) — New file: TriG fixture with RDF reification representation (2 named graphs, 15 triples).
- [ontology/examples/benchmark-rdf-star.trig](../../../../ontology/examples/benchmark-rdf-star.trig) — New file: TriG fixture with RDF-star representation (2 named graphs, 13 triples).
- [ontology/competency-questions/benchmark-queries.rq](../../../../ontology/competency-questions/benchmark-queries.rq) — New file: 18 SPARQL queries (6 patterns × 3 representations) plus UPDATE INSERT examples.

## Testing

- **Test Type:** Jena syntax validation + SPARQL query design review.
- **Validation Performed:**
  - All three TriG fixtures pass `docker compose run --rm jena riot --validate` (Jena 6.1.0, exit code 0 for all three).
  - The RDF-star fixture uses Turtle-star syntax (`<< ... >>`) and validates successfully with Jena's native RDF-star support.
  - The benchmark queries cover all six query patterns from the lifecycle competency questions (CQ-TEMP-001, CQ-TEMP-002, CQ-TEMP-004, CQ-REV-001, CQ-EV-002) adapted to assertion-level metadata.
  - The query file uses SPARQL comment delimiters consistent with the `query_blocks()` parser in `validate_ontology.py` for future automated validation.
  - The shared scenario (Requirement + validFrom + reviewer + ontology version) is a minimal but representative subset of the lifecycle use case, ensuring the benchmark results generalize to Sprint 2's full provenance requirements.
- **Status:** Awaiting human decision (S2-06).

## Additional Notes

- The primary recommendation (REIF) is driven by two non-negotiable Sprint 2 constraints: v0.1 backward compatibility (32 checks must pass) and SHACL compatibility (S2-11–S2-14 require native SHACL shapes). STAR fails on SHACL; AN fails on backward compatibility.
- The RDF-star fixture validates today in Jena 6.1.0, confirming that the toolchain supports the syntax. If SHACL 2.0 or a Jena extension adds quoted triple targets, STAR becomes the strongest candidate across all dimensions.
- The recommended SHACL consistency shape (§10.4 in the benchmark) should be implemented regardless of the chosen representation — it guards against the duplication risk in REIF and STAR, and serves as a data-quality check for any representation.
- This benchmark intentionally defers the human decision to S2-06. The analysis is structured so the reviewer can:
  - Accept the REIF recommendation and proceed to S2-07.
  - Choose STAR with the understanding that SHACL shapes will use SPARQL constraints.
  - Choose AN with the understanding that v0.1 queries must be migrated.
  - Request additional evidence (e.g., performance benchmarks on 10K-triple datasets, or a prototype of the SHACL SPARQL constraints for STAR).
