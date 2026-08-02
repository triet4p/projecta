# Task Summary: S5-29 — Add end-to-end M3 system tests

**Sprint:** Sprint 5
**Task:** S5-29

## Summary of Work

Added an opt-in real HTTP M3 acceptance harness for untyped-note extraction,
explicit abstention/zero-candidate behavior, idempotent replay, provider
failure handling, bounded link-context reads, and project-negative coverage.
The test requires `PROJECTA_M3_E2E=1`, so canonical CI never depends on a live
provider or credential. When enabled, provider outage is a failure rather than
a skip; the test validates extraction replay, candidate validation, rejection,
history, and canonical link-context IDs over HTTP.

## Files Modified

- `apps/api/tests/test_m3_e2e.py`

## Testing

- **Default:** skipped unless a real API URL and explicit M3 opt-in are set.
- **Static:** `git diff --check` passed.
