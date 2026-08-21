# Task Summary: S12-RM-30 — Implement Offline f12 Diagnostic Remediation

**Sprint:** Sprint 12
**Task:** S12-RM-30

## Summary of Work

Implemented the RM-29-approved offline diagnostic scope in a new versioned
path. Schema failures now map to nine finite sanitized reason codes and
evidence failures to ten finite materializer reason codes. The historical six
schema-invalid and 17 unsupported-evidence findings are intentionally mapped
to `validation_detail_unavailable` and `materializer_detail_unavailable`; the
implementation does not invent their missing raw causes.

The runtime-only evidence diagnostic preserves typed endpoint spans, source
proof and denominator reconciliation while emitting no source text, trigger
quote, raw provider payload or raw validation detail. The historical report v6
and guarded live runner remain untouched.

## Files Modified

* `scripts/s12_f12_rm30_diagnostic_remediation.py` — finite reason classifiers,
  runtime-only evidence diagnostics and sanitized historical report builder.
* `scripts/tests/test_sprint12_rm30_offline_diagnostics.py` — deterministic
  mock tests for all reason-code families, redaction, unknown fail-closed,
  arm/control separation, reconciliation and report immutability.
* `evaluation/sprint-12/harness/s12-f-12-offline-diagnostic-report.schema.v1.json` —
  new closed sanitized report schema.
* `evaluation/sprint-12/optimization/s12-f-12-rm30-offline-diagnostic-report.v1.json` —
  deterministic historical sanitized report.
* `evaluation/sprint-12/optimization/s12-f-12-rm30-offline-remediation.v1.json` —
  digest-bound implementation package pending owner review.
* `evaluation/sprint-12/current-state-next-rm30.v1.json` and G5 v18 preparation
  artifacts — explicitly non-authoritative next-state snapshots.
* Sprint plan/current-state/handoff docs — RM-30 completion and RM-31 gate.

## Testing

* **RM-30 deterministic tests:** `24 passed` with one environment-only
  `.pytest_cache` permission warning.
* **Combined safe regression:** `63 passed` across RM-28/RM-29/RM-30,
  document consistency, Phase F and spent-authorization tests.
* **Report validation:** new report schema validates with zero errors; generated
  report equals persisted v1 artifact and all accounting reconciles.
* **Safety:** immutable report digest remains
  `sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`;
  accounting remains 144 calls and 0 retries; no provider or runner execution.
* **Diff hygiene:** `git diff --check` passed after final edits.
  `ruff` is unavailable in this environment and was not claimed as passing.

## Next Gate

RM-31 owner review of the RM-30 implementation. No superseding lineage,
preregistration, freeze, authorization, provider execution, validation,
held-out access, Stage B, selection or promotion is authorized.
