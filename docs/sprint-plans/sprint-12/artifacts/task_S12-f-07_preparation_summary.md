# S12-f-07 Preparation — Development Error Backlog and Execution Package

**Status:** `S12_F07_COMPLETED_REJECTED_S12_F08_PREREGISTERED_NOT_EXECUTED`

## Scope

Created a development-only error backlog and a guarded S12-f-07 execution
package from the persisted S12-73, S12-77 and S12-f-06 reports. The analysis
and package preparation made no provider calls, did not inspect held-out data,
and did not modify gold or ontology artifacts.

## Artifacts

- [`development-error-analysis.v1.json`](../../../../evaluation/sprint-12/optimization/development-error-analysis.v1.json)
- [`development-error-analysis.v1.md`](../../../../evaluation/sprint-12/optimization/development-error-analysis.v1.md)
- [`s12-f-07-relation-prompt-preregistration.v1.json`](../../../../evaluation/sprint-12/optimization/s12-f-07-relation-prompt-preregistration.v1.json)
- [`s12-f-07-relation-prompt-preregistration.v2.json`](../../../../evaluation/sprint-12/optimization/s12-f-07-relation-prompt-preregistration.v2.json)
- [`experiment-registry.v6.json`](../../../../evaluation/sprint-12/optimization/experiment-registry.v6.json)
- [`g5-packet.v6.json`](../../../../evaluation/sprint-12/optimization/g5-packet.v6.json)
- [`s12-f-07-authorization.v1.json`](../../../../evaluation/sprint-12/optimization/s12-f-07-authorization.v1.json)
- [`experiment-registry.v7.json`](../../../../evaluation/sprint-12/optimization/experiment-registry.v7.json)
- [`g5-packet.v7.json`](../../../../evaluation/sprint-12/optimization/g5-packet.v7.json)
- [`s12-f-07-authorization.v2.json`](../../../../evaluation/sprint-12/optimization/s12-f-07-authorization.v2.json)
- [`s12-f-07-scoring-erratum.v1.json`](../../../../evaluation/sprint-12/optimization/s12-f-07-scoring-erratum.v1.json)
- [`experiment-registry.v8.json`](../../../../evaluation/sprint-12/optimization/experiment-registry.v8.json)
- [`g5-packet.v8.json`](../../../../evaluation/sprint-12/optimization/g5-packet.v8.json)
- [`s12-f-08-relation-prompt-preregistration.v1.json`](../../../../evaluation/sprint-12/optimization/s12-f-08-relation-prompt-preregistration.v1.json)
- [`s12-f-08-authorization.v1.json`](../../../../evaluation/sprint-12/optimization/s12-f-08-authorization.v1.json)
- [`s12-f-08-prompt-v5-composed-relation-contract.v1.txt`](../../../../evaluation/sprint-12/optimization/s12-f-08-prompt-v5-composed-relation-contract.v1.txt)
- [`s12-f-07-prompt-v4-relation-decision-rubric.v1.txt`](../../../../evaluation/sprint-12/optimization/s12-f-07-prompt-v4-relation-decision-rubric.v1.txt)
- [`sprint12_development_error_analysis.py`](../../../../scripts/sprint12_development_error_analysis.py)
- [`prepare_sprint12_f07_execution_package.py`](../../../../scripts/prepare_sprint12_f07_execution_package.py)
- [`run_sprint12_f07_prompt_experiment.py`](../../../../scripts/run_sprint12_f07_prompt_experiment.py)

## Result

All 288 persisted report case-runs are accounted. Seventeen missing outputs are
retained as fail-explicit records. Relation errors recur on positive-relation
cases across the available development evidence, while exact entity-type and
predicate/endpoints confusion is not recoverable from the sanitized aggregate
reports and is explicitly routed to evaluator instrumentation.

The single approved direction was a prompt-only relation decision rubric:
`deepseek-v4-flash`, control `m3.prompt.v3.supersession-guard`, candidate
`m3.prompt.v4.relation-decision-rubric`, provider-default sampling, and all
other dimensions fixed. Stage A was executed once for 16 cases × 3 paired runs
per arm, with no retry, producing 96 case-runs. It is now closed as
`COMPLETED_REJECTED`; it must not be fixed-and-rerun. The frozen execution
package was commit `2b8ca5a14f150b372645186fa6acbbffb7fa8914`. Prompt v4 was
implemented and digest-bound; the evaluator now supports the composed v5 path
and emits sanitized predicate-level relation instrumentation. Primary scoring
is fail-closed over all 48 case-runs per arm; paired common-valid scoring is
sensitivity-only. Candidate and control hard gates are separate, and control
failure degrades comparison integrity without becoming a candidate hard-gate
failure.

Authorization v1 remains immutable historical evidence; authorization v2 bound
the frozen commit, registry v7 and G5 v7. Registry/G5 v8 closes S12-f-07 with
no Stage B or candidate selection, binds the aggregate and all six report
digests, and records the scoring erratum. The erratum corrects entity
aggregation while retaining relation values as provisional because raw
predictions were not retained. S12-f-08 is preregistered with composed prompt
v5, stronger relation/supersession gates, and remains unauthorized and
unexecuted pending pricing.

## Validation

- `python -m pytest scripts/tests/test_sprint12_development_error_analysis.py -q` — passed (2 tests).
- `python -m pytest scripts/tests/test_sprint12_f07_execution_contract.py scripts/tests/test_sprint12_f08_contract.py scripts/tests/test_sprint12_phase_e_contract.py -q` — passed (30 tests).
- `python -m pytest scripts/tests -q` — passed (160 tests).
- Offline closure validation — passed; registry/G5 v8, immutable aggregate and six report digests, f08 preregistration and pending authorization are bound.
- JSON parsing for all generated JSON artifacts — passed.
- No provider calls were made while closing S12-f-07 or preregistering S12-f-08.
- `git diff --check` — passed.

The pytest run emitted only an environment warning because the local
`.pytest_cache` path was not writable; the tests themselves passed.
