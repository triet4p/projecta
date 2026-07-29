# Task Summary: S2-06 — Decide the Assertion Representation

**Sprint:** Sprint 2 — Governed Knowledge Lifecycle
**Task:** S2-06 — Decide the Assertion Representation

## Summary of Work

Human reviewer evaluated the S2-05 benchmark analysis and selected **RDF Reification (`rdf:Statement`)** as the assertion metadata representation for v0.2. The decision was recorded via `$log-decision` in `.agents/memory/decisions.md` with timestamp 2026-07-28.

The chosen representation was the primary recommendation from the benchmark: it preserves all 32 Sprint 1 checks (v0.1 backward compatibility), supports native SHACL shapes via `sh:targetClass rdf:Statement` (required by S2-11–S2-14), and is supported by every RDF tool since 1999. The duplication risk (value in both direct triple and `rdf:object`) is mitigated by a SHACL consistency shape.

Two deferred re-evaluations were recorded: RDF-star in Sprint 3+ (pending W3C standardization and SHACL quoted-triple support) and Assertion Node for v1.0 (when breaking query-surface changes are permitted).

## Files Modified

- [.agents/memory/decisions.md](../../../../.agents/memory/decisions.md) — Appended new decision entry: "Use RDF reification (rdf:Statement) for v0.2 assertion metadata."

## Testing

- **Test Type:** Human decision (no automated test).
- **Status:** Approved.

## Additional Notes

- This decision unblocks S2-07 (term inventory), S2-09 (vocabulary implementation), S2-11–S2-14 (SHACL shapes), and S2-15 (competency tests) — all of which depend on knowing which representation to use for assertion metadata.
- The decision log includes explicit deferred re-evaluation triggers (W3C RDF-star Recommendation, Jena SHACL quoted-triple support) so future sprints know when to revisit.
