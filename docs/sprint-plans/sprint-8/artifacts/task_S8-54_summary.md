# Task Summary: S8-54 — Approved Note semantic contract

**Status:** Complete

Semantic Core now accepts an optional title in the existing capture record,
while preserving the two-argument legacy constructor/default `Quick Note`.
Structured commits use the same named-graph transaction and released SHACL
validation for source, evidence, candidate, project, author, time, and
provenance. A failed validation occurs before any graph update.

Validation: Semantic Core compile, Spotless, and `mvn verify` pass.
