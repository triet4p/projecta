# Task Summary: S12-RM-40 — Offline Runtime Reconciliation Remediation

**Status:** complete; implementation package prepared; RM-41 owner review
pending

RM-39 approved offline runtime remediation and deterministic regression work
only. RM-40 implemented a new versioned offline path without mutating the
issued v8 runner/schema/authentication, RM-36 execution evidence, spent
authorization or historical v6 report.

## Implementation

`scripts/s12_f12_rm40_offline_runtime.py` derives the exact semantic-pair set
with the same greedy signature matching used by `score_relations`. It diagnoses
evidence only for those pairs and reconciles finite reason totals with the
scorer's `unsupported + missing` count. Non-exact, wrong, extra and missing
relations are excluded from that evidence domain. Entity metadata is projected
to `(start,end)` before classification, malformed values fail closed to
`materializer_detail_unavailable`, and output contains no raw source, payload or
validation detail.

The package and non-authoritative state snapshots are:

- `evaluation/sprint-12/optimization/s12-f-12-rm40-offline-runtime-package.v1.json`
- `evaluation/sprint-12/current-state-next-rm40.v1.json`
- `evaluation/sprint-12/optimization/g5-packet.v27.rm40-offline-runtime.json`

The safe regression suite passes 10 tests. The prospective custody contract
records 144 planned provider calls, 96 relation branches, one persist, zero
retry, and overwrite rejection while actually making zero calls. RM-41 must
review this package before any lineage preparation or execution authority.
