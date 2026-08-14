# Sprint 12 Phase E Evaluation Harness

**Version:** `s12.evaluator.v1`

**Status:** `G5_PREPARATION_BLOCKED_BASELINE_UNAVAILABLE`

The harness in `scripts/sprint12_evaluator.py` is a deterministic, stdlib-only
boundary around the frozen development/validation fixture. It validates source
and manifest digests, split policy, schema versions, scenario references and
duplicate/leakage conditions before scoring any output.

It exposes extraction, ontology-mapping, scenario, retrieval, reviewer-utility
and operational metric functions. Every evidence report includes dataset,
manifest, evaluator and configuration digests, explicit case coverage and
missing-output counts. Raw source text and reviewer comments are rejected from
reviewer utility records and are never written to the report.

The baseline command is:

```text
uv run --script scripts/sprint12_evaluator.py
```

With no approved runtime configuration, this command deliberately emits
`NOT_EXECUTED_MISSING_RUNTIME_CONFIGURATION`. Fixture replay is not presented
as a `v0.6.0` baseline result.
