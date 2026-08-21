# Sprint 12 Phase E Evaluation Harness

**Version:** `s12.evaluator.v4`

**Current Sprint status:** `G5_F12_OFFLINE_REMEDIATION_APPROVED_IMPLEMENTATION_ONLY`

The harness is also prepared for G6, but G6 remains separately blocked by
external custody and the absence of a frozen passing candidate. Current state
is indexed in `evaluation/sprint-12/current-state.v1.json`.

The harness in `scripts/sprint12_evaluator.py` is a deterministic, stdlib-only
boundary around the frozen development/validation fixture. It validates source
and manifest digests, split policy, schema versions, scenario references and
duplicate/leakage conditions before scoring any output.

It exposes extraction, ontology-mapping, scenario, retrieval, reviewer-utility
and operational metric functions. Every evidence report includes dataset,
manifest, evaluator and configuration digests, explicit case coverage and
missing-output counts. Raw source text and reviewer comments are rejected from
reviewer utility records and are never written to the report.

Relation diagnostics use `s12.relation-instrumentation.v4`: semantic matches,
wrong evidence spans, endpoint/predicate confusions, missing relations and
extra relations are mutually exclusive and include reconciliation totals.
Each scored case also carries sanitized gold/predicted signatures containing
predicate, endpoint types, offsets, evidence offsets, and the assigned error
class. Entity IDs, raw source text, and payloads are excluded. Historical
v1/v2/v3 reports remain bound to their original evaluator versions.

The baseline command is:

```text
uv run --script scripts/sprint12_evaluator.py
```

The historical baseline has since run and remains immutable at 105 valid
outputs out of 160, with 55 fail-explicit failures. The command's behavior is
configuration-dependent; a missing runtime configuration must still fail
explicitly and must never be presented as a model-quality result.
