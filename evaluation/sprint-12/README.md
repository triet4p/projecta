# Sprint 12 Dataset Contract

**Contract version:** `s12.v1`

**Status:** `G1_PACKET_READY_FOR_HUMAN_APPROVAL`

This directory contains the governed contract for the Sprint 12 business
semantic benchmark. It does not contain the held-out test cases or gold. Test
inputs and annotations remain under human custody until the approved G6
procedure permits one blinded run.

## Contract artifacts

- `schema/atomic-case.schema.json` defines one independently addressable note
  case and its atomic semantic gold.
- `schema/scenario-case.schema.json` defines one ordered project episode,
  graph checkpoints, review decisions and grounded competency answers.
- `coverage-matrix.v1.json` binds the G0 journeys to minimum quotas and slices.
- `annotation-guide.v1.md` defines gold-label decisions and counterexamples.
- `data-governance.v1.md` defines provenance, licensing, privacy, retention,
  leakage, split and custody controls.
- `metrics.v1.md` defines deterministic scoring and reporting behavior.

## Dataset contract rules

- Every case has a stable ID, schema version, origin, language, sensitivity,
  permission reference, split and content digest.
- Every evidence span uses zero-based, half-open Unicode code-point offsets and
  must reproduce the exact source slice.
- Gold uses released extraction types and relation predicates. Unsupported
  concepts are recorded as semantic gaps rather than force-fit.
- Model-assisted drafts require human rewriting and independent annotation.
- Validation and test cases are double-annotated and materially disputed cases
  are adjudicated by a third qualified reviewer.
- Development and validation artifacts may be repository-local only when they
  satisfy the privacy, provenance and leakage rules. Test payloads and gold are
  not stored in this repository.

## Current gate

The contract is ready for G1 review. S12-28 remains pending until the project
owner and semantic reviewer approve or revise the packet at
`docs/sprint-plans/sprint-12/g1-dataset-contract.md`.
