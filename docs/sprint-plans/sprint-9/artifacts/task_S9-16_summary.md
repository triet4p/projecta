# Task Summary: Automate SemVer tag releases

**Sprint:** Sprint 9 — Provider Runtime Truthfulness
**Task:** S9-16

## Summary of Work

Added a tag-driven GitHub Actions release workflow and a fail-explicit release
contract. Only exact `vA.B.C` tags can publish; every manifest and changelog
section must match, all component/repository/system gates must succeed, and the
GitHub Release body is rendered from the matching changelog section.

The clean system runner now generates all required process-scoped Compose
secrets, restores their prior state after cleanup, and captures bounded service
logs before cleanup on failure. Its final run also exposed and fixed an API-only
confirmation field leaking into the strict Semantic Core payload.

## Files Modified

* `.github/workflows/release.yml`
* `scripts/check_release_contract.py`
* `scripts/tests/test_check_release_contract.py`
* `scripts/run_system_tests.ps1`
* `apps/api/src/projecta_api/routes.py`
* `apps/api/tests/test_capture_contract.py`
* `.agents/memory/decisions.md`
* `.agents/memory/lessons-learned.md`

## Testing

* Release contract: 4 tests pass; `v0.4.0` renders the correct notes.
* Workflow syntax: actionlint 1.7.7 passes.
* Clean-volume system gate: ontology `140/140`, Semantic Core 49 tests, and
  Compose API journey `129 passed, 2 deselected`.
* Exact legacy confirmation payload regression: pass.

## Additional Notes

Publication is idempotent for an existing GitHub Release, but no release can be
created before every required job succeeds.
