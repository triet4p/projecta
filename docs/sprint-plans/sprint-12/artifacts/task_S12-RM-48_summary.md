# S12-RM-48 — Offline v6/v9 error comparison and remediation options

**Status:** prepared; pending S12-RM-49 owner review  
**Date:** 2026-08-22

RM-48 used only the immutable sanitized v6/v9 reports and deterministic
repository-visible analysis. The comparison artifact is
`evaluation/sprint-12/optimization/s12-f-12-rm48-error-comparison.v1.json`.

## Findings

- Both reports account for 144 provider calls, 144 responses and zero retries.
- Schema-invalid decreased 6 → 5; v9 finite diagnostics classify all five as
  `entity_span_out_of_source` in the predicted-entities Stage 1 arm.
- Invalid evidence increased 17 → 20. v9 records 14
  `evidence_does_not_contain_trigger` and 6
  `evidence_does_not_contain_endpoints`; v6 historical reason detail is
  unavailable.
- Seventeen evidence case-runs overlap between versions; v9 adds the first
  `s12-a-4035` run and runs 2–3 of `s12-a-4043`. Schema case-run clusters are
  reported by arm/stage without inferring causality.
- Gold-relations is a clean control in both reports. Threshold and all
  registered slice deltas are retained in the comparison.

The one-response schema reduction is not a quality-improvement claim because
invalid evidence increased and hard/threshold/slice gates still fail.

## Options prepared, not authorized

1. Harden finite offline diagnostics and report contracts.
2. Build deterministic offline materializer/scorer parity fixtures.
3. Stop provider experimentation and preserve the current evidence boundary.

The recommendation is to consider options 1 then 2 only after RM-49 review, and
to choose option 3 if offline parity cannot be demonstrated without withheld
payload/source or if no measurable next hypothesis exists.

## Governance

RM-48 authorizes no remediation implementation, superseding lineage,
preregistration, technical freeze, provider call, rerun, retry, validation,
held-out access, Stage B, selection or promotion. RM-49 is the next gate.
