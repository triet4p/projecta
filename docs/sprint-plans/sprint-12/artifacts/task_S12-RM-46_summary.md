# S12-RM-46 — Exact v9 Stage A execution

**Status:** Complete as a single-use execution fact; RM-47 owner decision pending

RM-46 ran the exact guarded v9 command once under the committed RM-45
authorization. The preflight returned `F12_RM45_AUTHORIZED_ZERO_CALL_PRECHECK`
with a clean tree, absent v9 output, exact execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`, and the frozen 19-blob runtime
binding.

```text
uv run --env-file .env --script scripts/run_sprint12_f12_stage_a_v9.py --authorization evaluation/sprint-12/optimization/s12-f-12-rm45-authorization.v9.json --output evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json
```

The invocation completed 144 provider calls and 96 relation branches, with
144 responses, 139 schema-valid responses, zero retries, zero pricing
failures, and total cost `$0.00599700` under the `$10.00` ceiling. The report
is JSON-Schema-valid and immutable at
`evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json`, digest
`sha256:84cb0667b8ee3469be5bdd4c3545a41012ba46bb07071508c41dca76fbf3761e`.

The result is `COMPLETED_REJECTED_HARD_GATE`: `schemaInvalid=5` and
`invalidEvidence=20`; thresholds and slice gates also fail. The schema
diagnostic is five `predicted-entities:entity_span_out_of_source` findings.
The evidence diagnostics are 14 gold-entity trigger-containment failures and
6 gold-entity endpoint-containment failures. Gold-relations integrity and the
cost ceiling pass. No raw provider payload, source text, held-out data, retry,
overwrite or downstream access was used.

RM-46 consumes the one RM-45 authorization and does not authorize rerun,
validation, held-out access, Stage B, candidate selection, promotion or any
quality claim. RM-47 must independently decide the next governed action. The
immutable v6 report remains preserved and the superseded v8 report remains
absent.

Machine evidence:

- `evaluation/sprint-12/optimization/s12-f-12-rm46-execution-transition.v1.json`
- `evaluation/sprint-12/current-state-next-rm46.v1.json` (non-authoritative)
- `evaluation/sprint-12/optimization/g5-packet.v32.rm46-execution.json` (non-authoritative)
- `scripts/tests/test_sprint12_rm46_execution.py` (`3 passed`)
