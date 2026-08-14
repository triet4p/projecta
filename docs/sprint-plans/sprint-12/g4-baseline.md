# Sprint 12 G4 Baseline Evaluation Review Packet

**Status:** `G4_APPROVED_WITH_LIMITATIONS_G5_PENDING`

**Gate:** G4 — Baseline Evaluation

## 1. Packet boundary

The packet binds the `s12.evaluator.v1` harness to dataset version
`s12.corpus.atomic.v1`, the frozen development/validation manifest and the
released `v0.6.0` boundary. The test split remains sealed and is not loaded.

| Evidence | Bound artifact | State |
| --- | --- | --- |
| Loader and integrity | `evaluation/sprint-12/harness/` | Implemented and self-tested |
| Metric contract | `harness/metric-contract.v1.json` | Versioned |
| Error taxonomy | `harness/error-taxonomy.v1.json` | Versioned |
| Baseline report | `baseline/baseline-report.v1.json` | Not executed |
| Baseline Markdown | `baseline/baseline-report.v1.md` | Prepared |

## 2. Measurement status

The repository does not contain an approved live runtime configuration for the
`v0.6.0` baseline. The runner therefore records
`NOT_EXECUTED_MISSING_RUNTIME_CONFIGURATION`, marks all 160 repository-visible
development/validation outputs as missing, and records one runtime-class
observation. This is a truthful preparation result, not a model-quality score.

No hard invariant, slice metric, latency, cost or accepted-candidate result is
claimed until the released prompt and runtime are supplied unchanged and the
baseline is executed.

## 3. Validation evidence

```text
uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_e_contract.py
uv run --script scripts/sprint12_evaluator.py
```

The self-tests cover unknown schema, tampered source, split policy, duplicate
and leakage digests, cross-file references, missing output, malformed metric
inputs, reviewer raw-data rejection, finite error taxonomy and digest-bound
reports.

## 4. G4 acceptance checklist

- [x] Versioned loader and deterministic integrity checks are implemented.
- [x] Metric families and explicit missing-output behavior are implemented.
- [x] Evidence JSON/Markdown is bound to dataset/configuration digests.
- [x] Error taxonomy is finite and versioned.
- [x] Draft G4 packet is prepared.
- [ ] `v0.6.0` baseline is executed on unchanged development/validation data.
- [ ] Baseline errors are classified from observed model/runtime outputs.
- [x] Project owner approves the truthful no-run measurement boundary with the
  limitation recorded below.
- [ ] Semantic reviewer approves a runtime-backed baseline quality measurement.

## 5. Approval record (S12-71)

| Field | Value |
| --- | --- |
| G4 outcome | `APPROVED_WITH_LIMITATIONS` |
| Baseline status | `NOT_EXECUTED_MISSING_RUNTIME_CONFIGURATION` |
| Project owner | Explicit approval recorded in Codex task on 2026-08-14 |
| Semantic reviewer | _Awaiting baseline evidence_ |
| Authorization after approval | No optimization or held-out evaluation unlock |
