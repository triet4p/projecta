# S12-RM-52 — Offline f12 closure packet and prioritized error backlog

**Status:** prepared; pending S12-RM-53 owner closure review  
**Date:** 2026-08-22

RM-52 prepared two non-authoritative, offline-only artifacts under the RM-51
Option C stop:

- `evaluation/sprint-12/optimization/s12-f-12-rm52-offline-closure.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm52-error-backlog.v1.json`

The closure packet binds the immutable v6 report, the three-call/no-report v8
execution fact, the immutable v9 report, RM-47/RM-51 decisions and
transitions, rejected RM-50 artifacts, and all spent v7/v8/v9 authorizations.
Known cost is `$0.01192200`; v8 aggregate cost remains unknown because no
report was persisted. The v8 report path is absent and no report was created
or restored by RM-52.

The backlog distinguishes offline bugs fixed in bounded scopes, residual
product-quality failures, tooling/governance lessons and external custody
blockers. It records five v9 out-of-source entity spans, 14 trigger-containment
failures, six endpoint-containment failures, the RM-50 accounting immutability
gap, unknown prompt/model causality, Windows Git-blob custody, unsafe
historical tests, and the external G6 held-out/human-evidence block.

Safe schema/custody tests verify both artifacts, source digests, v8 absence,
RM-51 governance locks and no provider call; the combined targeted safe suite
passes 92 tests (with only the known Windows `.pytest_cache` permission
warning). RM-53 is the next gate. RM-52
does not complete Sprint 12, G5 or G6 and establishes no quality or candidate
claim.
