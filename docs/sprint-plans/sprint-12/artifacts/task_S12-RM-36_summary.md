# Task Summary: S12-RM-36 — Execute Exact v8 Stage A Once

**Task:** S12-RM-36  
**Status:** complete; one authorized invocation failed before report persistence; RM-37 owner decision pending  
**Date:** 2026-08-22

## Scope

RM-36 performed the single execution permitted by the immutable RM-35
authorization. The RM-35 owner review, authorization and transition were not
mutated. Zero-call pre-execution checks passed: the worktree was clean, the v8
output was absent, v6 custody was intact, the authorization and runtime
bindings matched, and all 22 exact runtime Git blobs matched the frozen
execution commit.

The exact command was invoked once:

```text
uv run --env-file .env --script scripts/run_sprint12_f12_stage_a_v8.py --authorization evaluation/sprint-12/optimization/s12-f-12-rm35-authorization.v8.json --output evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json
```

It exited with code `1` at the first predicted-entities arm diagnostic
reconciliation with:

```text
F12StageAV8Error: evidence reason counts do not reconcile with arm materializer failures
```

The runner completed three captures before the first arm record raised:
stage-1 predicted entities, stage-2 predicted entities, and stage-2 gold
entities. Therefore the execution evidence records 3 provider calls attempted
and 3 responses received. No aggregate relation-branch result or cost can be
claimed because the report/accounting materializer did not complete. No retry
or overwrite occurred, and no v8 report was persisted.

## Evidence and governance

The machine execution fact is
`evaluation/sprint-12/optimization/s12-f-12-rm36-execution-transition.v1.json`.
The non-authoritative post-run snapshots are:

- `evaluation/sprint-12/current-state-next-rm36.v1.json`
- `evaluation/sprint-12/optimization/g5-packet.v24.rm36-execution-failure.json`

The consumed RM-35 authorization is spent and non-reusable. Retry, rerun,
overwrite, validation, held-out access, Stage B, selection and promotion remain
closed. The v8 output remains absent. No quality, gate, candidate or
business-quality conclusion can be inferred from the failed invocation.

Historical v6 remains immutable at
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`,
with 144 provider calls and zero retries. RM-37 is the next owner gate. It must
decide the next governed action; RM-36 does not authorize a retry, remediation
run, Stage B, validation, held-out evaluation, selection or promotion.
