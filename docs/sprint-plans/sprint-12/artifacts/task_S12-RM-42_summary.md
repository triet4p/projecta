# Task Summary: S12-RM-42 — Corrected v9 Runtime-Lineage Preparation

**Status:** complete; unissued v9 lineage prepared; RM-43 owner issuance review
pending

RM-41 approved preparation of a corrected superseding runtime lineage only.
RM-42 implemented a guarded v9 runtime that integrates RM-40 behavior into the
actual execution path, then prepared exact-commit v9 custody artifacts without
provider execution.

## Runtime implementation

The runtime commit is:

- `2464022dc2cc7fb7c13565accaa648c242e0ec16`

It contains the guarded v9 runner, closed report and authorization schemas, and
deterministic mocked E2E coverage. The runner calls `rm40.diagnose_arm` from
the arm-record path; RM-40 remains a diagnostic dependency, not a standalone
execution lineage.

Focused runtime and reconciliation tests pass (`29 passed` across v9, RM-40
and RM-38 suites). The mocked E2E reaches the closed v9 report schema and
persists once with exactly 144 mock captures, zero retries and no provider.

## Custody artifacts

- `evaluation/sprint-12/optimization/s12-f-12-rm42-execution-package.v9.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm42-preregistration.v9.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm42-technical-freeze.v9.json`
- `scripts/preflight_sprint12_f12_rm42.py`
- `evaluation/sprint-12/current-state-next-rm42.v1.json`
- `evaluation/sprint-12/optimization/g5-packet.v28.rm42-v9-preparation.json`

The package separates exact Git-blob runtime bindings from working-tree
preparation evidence. The preflight passes with 19 runtime blobs, 9
preparation entries, zero provider calls, zero retries, and absent v9 output.
The immutable v6 report remains digest
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`;
the failed v8 output remains absent.

## Next gate

RM-43 must independently review and issue the v9 preregistration/freeze, then a
separate exact-commit authorization review is required before any provider
execution. Validation, held-out, Stage B, selection and promotion remain
closed.
