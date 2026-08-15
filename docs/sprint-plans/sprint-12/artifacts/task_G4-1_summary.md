# G4.1 — Contract Alignment and Failure Diagnosis

G4.1 is closed as `CONTRACT_ALIGNED_STABILITY_FAILED`. The historical
`v0.6.0` baseline is locked at 160 cases
with 55 missing outputs and is not rerun. A synthetic-only diagnostic sample of
7 schema failures plus 16 stratified invalid-evidence cases was captured.

The opt-in `m3.v2` contract now supports local entity candidate IDs, exact
quote/occurrence evidence with server-side materialization across all candidate
categories, and relation normalization against local candidates. The historical
contract evidence and current prompt-experiment evidence are now separated in
the packet under explicit scope labels. The current guarded-prompt 32-case
follow-up has `3 schema_invalid` and `0 invalid_evidence`, so validation and
freeze stay blocked.

The supersession amendment remains versioned as `s12.corpus.atomic.v2`; the v1
corpus is unchanged. The G5 registry records `s12-f-01` as
`COMPLETED_STABILITY_FAILED`, binds the 3x8 and 3x32 protocol variance, and
records the candidate as available but rejected on hard invariants rather than
unavailable.

## Testing

Focused API/contract tests pass, including a two-entity local-relation
end-to-end path and the governance consistency checks. The G4.1 packet and
diagnostic artifacts are synthetic-only and preserve `humanEvidence: false`.
