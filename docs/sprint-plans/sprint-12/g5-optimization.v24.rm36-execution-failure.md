# Sprint 12 G5 — RM-36 v8 Execution Failure Snapshot

**Status:** `G5_F12_V8_EXECUTION_FAILED_PENDING_RM37_OWNER_DECISION`

This document describes the non-authoritative RM-36 post-run snapshot. The
authoritative RM-35 packet and authorization records remain immutable evidence
of the authority that existed before the one permitted invocation. The machine
snapshot is
`evaluation/sprint-12/optimization/g5-packet.v24.rm36-execution-failure.json`.

RM-36 passed its zero-call preflight and invoked the exact v8 runner once with
the RM-35 authorization. The process exited with code `1` while materializing
the first predicted-entities arm because evidence reason counts did not
reconcile with arm materializer failures. Runner control flow shows three
completed captures before that failure, so the execution fact records 3 calls
attempted and 3 responses received. The report was not persisted; aggregate
relation branches, cost and complete accounting are therefore unavailable.

The authorization is spent and cannot be reused. No retry, rerun or overwrite
is authorized. Validation, held-out access, Stage B, selection and promotion
remain closed. Historical v6 is preserved unchanged with 144 calls, 96
relation branches and zero retries. RM-37 must independently review this
failure fact before any further governed action.
