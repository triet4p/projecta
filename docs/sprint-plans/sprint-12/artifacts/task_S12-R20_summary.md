# S12-R20 — S12-f-09 preregistration

Status: complete

S12-f-09 is preregistered against frozen v3 with the accepted control prompt
`m3.prompt.v3.supersession-guard`, `deepseek-v4-flash`, m3.v2 and the current
evaluator/metric contract. The sole experimental dimension is `tool`: the
candidate uses the server-owned relation-evidence materializer while the
control retains legacy LLM-authored relation evidence.

Stage A is fixed to 48 frozen development cases, 3 paired interleaved runs,
144 case-runs per arm, one attempt per case and no retries. Pricing, dataset,
evaluator, prompt and materializer digests are bound; semantic relation,
evidence support/exactness, entity, abstention, hallucination and slice floors
are explicit. Execution remains unauthorized, with held-out access and all
prompt/model/sampling sweeps prohibited.

Changed artifacts:

- `scripts/preregister_sprint12_f09.py`
- `scripts/tests/test_sprint12_f09_preregistration.py`
- `evaluation/sprint-12/optimization/s12-f-09-relation-evidence-preregistration.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: preregistration contract tests, full API/scripts suites, Ruff, and
`git diff --check`. No provider execution or held-out access was used.
