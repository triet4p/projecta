# Sprint 12 G4 Baseline Evaluation Review Packet

> Historical gate snapshot. Do not use this packet as the current Sprint 12
> dashboard; see [Sprint 12 Current State](current-state.md).

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
| Baseline report | `baseline/baseline-report.v1.json` | Runtime-backed; 160 accounted, 55 missing outputs |
| Baseline Markdown | `baseline/baseline-report.v1.md` | Prepared |

## 2. Measurement status

The released `v0.6.0` runtime was executed against all 160 repository-visible
development/validation cases. The report is
`RUNTIME_BACKED_WITH_FAILURES`: 105 cases produced valid normalized output and
55 cases were fail-closed as missing outputs (`48 invalid_evidence`, `7
schema_invalid`). This is a truthful runtime measurement, not a passing
model-quality result.

Split integrity, dataset digest binding and held-out nonleakage pass. Schema
validity fails, so no accepted-candidate or optimization result is claimed
until the model-output failures are resolved and the baseline is rerun.

## 3. Validation evidence

```text
uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_e_contract.py
uv run --project apps/api --env-file .env python scripts/sprint12_evaluator.py
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
- [x] `v0.6.0` baseline is executed on unchanged development/validation data.
- [x] Baseline errors are classified from observed model/runtime outputs.
- [x] Project owner approves the truthful no-run measurement boundary with the
  limitation recorded below.
- [ ] Semantic reviewer approves a runtime-backed baseline quality measurement.

## 5. Approval record (S12-71)

| Field | Value |
| --- | --- |
| G4 outcome | `APPROVED_WITH_LIMITATIONS` |
| Baseline status | `RUNTIME_BACKED_WITH_FAILURES` |
| Case accounting | `160 total; 105 valid outputs; 55 missing outputs` |
| Observed failures | `48 invalid_evidence; 7 schema_invalid` |
| Project owner | Explicit approval recorded in Codex task on 2026-08-14 |
| Semantic reviewer | _Awaiting baseline evidence_ |
| Authorization after approval | No optimization or held-out evaluation unlock; schema-valid rerun required |
