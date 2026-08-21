# S12-R17 — stale preregistration supersession

Status: complete

The versioned supersession packet closes S12-f-02 (context), S12-f-03
(agent-workflow) and S12-f-04 (generic tool) before any v3 experiment can open.
Each historical entry is bound by digest to `experiment-registry.v10.json`,
retains its old v2 dataset/manifest binding, and is explicitly marked closed in
the new amendment. The historical registry itself is not rewritten.

The replacement path is S12-f-09 on frozen v3, but the packet keeps provider
execution, held-out access and test inspection false. R18/R19 must implement and
test the deterministic relation-evidence tool before R20 preregistration.

Changed artifacts:

- `scripts/supersede_sprint12_stale_preregs.py`
- `scripts/tests/test_sprint12_stale_prereg_supersession.py`
- `evaluation/sprint-12/optimization/s12-f-02-04-v3-supersession.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: historical-entry digest tests, full `scripts/tests` suite, Ruff,
and `git diff --check`. No provider execution or held-out access was used.
