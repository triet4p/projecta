# Sprint 12 G5 Optimization Packet v9

S12-f-07 remains `COMPLETED_REJECTED` and immutable. S12-f-08 was authorized for
one development-only Stage A run, completed with 96/96 case-runs, and failed
the positive-relation gates. It is now closed with no Stage B or selection.

- Evaluator: `s12.evaluator.v2`
- Runner: [`run_sprint12_f08_prompt_experiment.py`](../../scripts/run_sprint12_f08_prompt_experiment.py)
- Execution package commit: `84e589bce954d8e23ad734eeb01b0711140dd854`
- Pricing: [`s12-f-08-pricing-deepseek-v4-flash.v1.json`](../../../evaluation/sprint-12/optimization/s12-f-08-pricing-deepseek-v4-flash.v1.json)
- Registry: [`experiment-registry.v9.json`](../../../evaluation/sprint-12/optimization/experiment-registry.v9.json)
- Authorization: [`s12-f-08-authorization.v2.json`](../../../evaluation/sprint-12/optimization/s12-f-08-authorization.v2.json)

The runner requires three usage classes—cache-hit input, cache-miss input and
output—and refuses execution when `.env` does not match the bound pricing
artifact. It performs six interleaved invocations (`control → candidate`,
`candidate → control`, `control → candidate`), never retries and refuses to
overwrite reports or the aggregate.
