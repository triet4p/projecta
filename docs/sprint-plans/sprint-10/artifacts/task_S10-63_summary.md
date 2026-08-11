# Task Summary: S10-63 — Isolated recovery runner

Added `scripts/run_sprint10_recovery.ps1` and the disposable
`connector_recovery_fixture.py` probe. The runner creates explicitly named
temporary PostgreSQL source/restore containers, migrates and seeds state,
backs up database plus evidence only after explicit quiescence confirmation,
tears down the source, restores with the isolated confirmation guard, verifies
the exact restored evidence reference plus replay/cursor/run invariants,
scans database logs, and cleans all temporary state without masking the first
failure.

Testing: recovery-runner contract tests passed. The latest complete run passed
source migration/seed, PostgreSQL plus evidence backup, source teardown,
isolated restore, state verification, replay (`replayed`), cursor/run/evidence
invariants, forbidden-log scan, and deterministic cleanup. Its evidence is in
`s10-63-recovery.json` with `status=passed` and all 8 runner steps at exit 0.
