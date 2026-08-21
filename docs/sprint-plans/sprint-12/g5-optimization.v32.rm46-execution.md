# Controlled Optimization Review Packet v32 — RM-46 v9 Execution

**Status:** `G5_F12_V9_STAGE_A_EXECUTED_COMPLETED_REJECTED_HARD_GATE_PENDING_RM47_OWNER_DECISION`

## Decision boundary

RM-46 consumed the single RM-45 authorization with one exact v9 development
Stage A invocation. The execution fact and report are immutable, while this
packet and the next-state snapshot are non-authoritative until RM-47 makes the
separate owner post-run decision.

## Execution evidence

- Command: `uv run --env-file .env --script scripts/run_sprint12_f12_stage_a_v9.py --authorization evaluation/sprint-12/optimization/s12-f-12-rm45-authorization.v9.json --output evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json`
- Execution commit: `f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`
- Provider calls / responses: `144 / 144`
- Relation branches: `96`
- Schema-valid responses: `139`
- Retry count: `0`
- Total cost: `$0.00599700` (ceiling `$10.00`)
- Report digest: `sha256:84cb0667b8ee3469be5bdd4c3545a41012ba46bb07071508c41dca76fbf3761e`
- Report schema validation: pass

The report status is `COMPLETED_REJECTED_HARD_GATE`. It fails
`schemaInvalid=5`, `invalidEvidence=20`, `thresholds` and `sliceGates`; gold
relations integrity, cost ceiling, raw-data policy and held-out custody pass.

## Governance boundary

The RM-45 authorization is spent and non-reusable. Retry, rerun, output
overwrite, validation, held-out access, Stage B, candidate selection,
promotion and downstream access remain false. No accuracy improvement,
candidate, business-quality or tenant-readiness claim is established.

RM-47 is the only next task: owner review of the immutable report and this
execution fact. The v6 report remains immutable historical custody and v8 has
no persisted report.

## Records

- Execution transition:
  `evaluation/sprint-12/optimization/s12-f-12-rm46-execution-transition.v1.json`
- Non-authoritative state:
  `evaluation/sprint-12/current-state-next-rm46.v1.json`
- Non-authoritative machine packet:
  `evaluation/sprint-12/optimization/g5-packet.v32.rm46-execution.json`
