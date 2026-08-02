# S5-33 — Final M3 approval gate

Implementation, validation, and the final ontology approval are complete. The
user approved the v0.4 ontology and Sprint 5 M3 boundary on 2026-08-02.

Release record: v0.4 ontology semantics, provider endpoint/model configuration,
evaluation thresholds, bounded candidate boundary, runtime SHACL integration,
and lifecycle path are implemented. The corrective pass fixed exact-evidence
transport, generated Turtle, structured idempotent replay parsing, and the
trusted link-context API read. A clean canonical Compose run passed ontology
`119/119`, Semantic Core `35/35`, and API E2E `51/51`.

The earlier provider-facing `400 INVALID_REQUEST` was an implementation error
classification and is fixed; invalid provider output now fails as
`503 SEMANTIC_CONTRACT_UNAVAILABLE`. The previous live non-exact-span finding is
invalid because the gold fixture used offset 45 for a 44-code-point sentence.
The gold and evaluator are corrected. Release remains blocked only on an
explicit live-quality rerun; the prior wrong entity type remains a quality risk
until that rerun passes or is explicitly accepted/revised. The Windows TDB2
cleanup lock remains an environment-specific teardown risk, not an assertion
failure.
