# Task Summary: S12-RM-26 — Execute One Authorized f12 Stage A

**Sprint:** Sprint 12
**Task:** S12-RM-26

## Summary of Work

Loaded the documented local `.env` source through `uv run --env-file .env` and
executed the exact RM-25-authorized S12-f-12 development Stage A once with the
v6 guarded runner. The run completed all 144 provider calls and preserved the
sanitized report v6, which is schema-valid but correctly rejected by hard,
threshold and slice gates. No retry or overwrite was attempted.

## Files Modified

* `evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json` — immutable sanitized one-run report.
* `evaluation/sprint-12/optimization/s12-f-12-stage-a-execution-transition.v1.json` — execution custody, accounting and governance transition.
* `docs/sprint-plans/sprint-12/current-state.md` — current post-run state and locked next gate.
* `evaluation/sprint-12/current-state.v1.json` — machine-readable post-run state.
* `evaluation/sprint-12/optimization/g5-packet.v14.json` — current G5 packet with report-bound evidence.
* `docs/sprint-plans/sprint-12/g5-optimization.v14.md` — human-readable post-run G5 packet.
* `docs/sprint-plans/sprint-12.md` — marked the one authorized execution complete and added the owner-decision gate.

## Testing

* **Report validation:** JSON Schema v6 passed; accounting and digest/custody checks passed.
* **Execution evidence:** 144 calls, 144 responses, 96 relation branches, 138 schema-valid responses, 144 usage-valid responses, 0 retries, 0 pricing failures.
* **Gate result:** `COMPLETED_REJECTED_HARD_GATE`; `schemaInvalid=6`, `invalidEvidence=17`, cost `$0.00592500` under `$10.00`.
* **Diff hygiene:** `git diff --check` passed.

## Additional Notes

The report remains immutable and contains no raw source text or provider
payloads. Validation, held-out access, Stage B, candidate selection and
promotion remain unauthorized. The next permitted action is a separate owner
decision on this report; any rerun requires a superseding package and new
authorization.
