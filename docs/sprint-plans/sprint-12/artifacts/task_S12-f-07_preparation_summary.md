# S12-f-07 Preparation — Development Error Backlog and Execution Package

**Status:** `EXECUTION_PACKAGE_FROZEN_STAGE_A_AUTHORIZED_NOT_EXECUTED`

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

The single approved direction is a prompt-only relation decision rubric:
`deepseek-v4-flash`, control `m3.prompt.v3.supersession-guard`, candidate
`m3.prompt.v4.relation-decision-rubric`, provider-default sampling, and all
other dimensions fixed. Stage A is authorized for 16 cases × 3 paired runs
with no retry but was not executed. The frozen execution package is commit
`2b8ca5a14f150b372645186fa6acbbffb7fa8914`. Prompt v4 is implemented and digest-bound;
the evaluator now supports v2, v3 and v4 through one versioned dispatch path
and emits sanitized predicate-level relation instrumentation. The v2
preregistration explicitly moves pricing from a pre-execution requirement to a
pre-selection requirement, with rationale. Primary scoring is fail-closed over
all 48 case-runs per arm; paired common-valid scoring is sensitivity-only.
Candidate and control hard gates are separate, and control failure degrades
comparison integrity without becoming a candidate hard-gate failure.

Authorization v1 remains immutable historical evidence; authorization v2 binds
the frozen commit, registry v7 and G5 v7. The package remains blocked from
selection/Stage B by the unbound pricing contract, while the Stage A runner
requires the final digest/case/split/profile preflight before any provider call.

## Validation

- `python -m pytest scripts/tests/test_sprint12_development_error_analysis.py -q` — passed (2 tests).
- `python -m pytest scripts/tests/test_sprint12_f07_execution_contract.py scripts/tests/test_sprint12_phase_f_contract.py scripts/tests/test_sprint12_phase_e_contract.py -q` — passed (44 tests).
- `python -m pytest scripts/tests -q` — passed (155 tests).
- Offline Stage A preflight — passed; 16 development cases, registry v7, G5 v7, frozen execution commit bound.
- JSON parsing for all generated JSON artifacts — passed.
- `git diff --check` — passed.

The pytest run emitted only an environment warning because the local
`.pytest_cache` path was not writable; the tests themselves passed.
