# S12-RM-07 Summary — Stage A Execution

## Outcome

The guarded CLI executed S12-f-10 Stage A exactly once against Approval B v1.
The execution produced the immutable sanitized report at
`evaluation/sprint-12/optimization/s12-f-10-stage-a-report.v5.json`.

## Execution evidence

- Provider calls: `48`.
- Branch outputs: `96`.
- Retry count: `0`.
- Provider failure classification: `schema_invalid` for all `96` mirrored
  branch outcomes.
- Actual cache-aware cost: `$0.0031325392`.
- Cost ceiling gate: `PASS` against `$10.00`.
- Shared-response digest gate: `PASS`.
- Raw sensitive data included: `false`.
- Held-out inspected: `false`.
- Report digest: `sha256:4bdb18175f76e78585c78775f5ab5106b24e2335d4eb6e1cd6528780e5736e9a`.

## Governance result

Stage A execution is complete. The schema-invalid provider result causes the
schema and semantic slice gates to fail closed. Comparison failure mirroring,
pricing, cost, retry, shared-response and custody gates remain intact. Stage B,
candidate selection, validation access and promotion remain closed. A separate
decision artifact and owner review are required before any subsequent action.
