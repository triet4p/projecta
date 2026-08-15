# Task Summary: S12-f-06 Sampling Stage A

**Sprint:** Sprint 12
**Task:** S12-f-06

## Summary of Work

Executed the approved single-variable sampling experiment using
`deepseek-v4-pro` for both control and candidate. The candidate changed only
sampling from provider defaults to `temperature=0.0` and `topP=1.0`. Stage A
used 8 development cases, 3 paired runs per variant, one attempt per case, and
no retry.

## Result

The explicit-sampling candidate had zero schema failures and zero missing
outputs, but semantic deltas were negative: entity macro F1 `-0.0714`,
abstention accuracy `-0.0774`, relation macro F1 `-0.0238`, and hallucination
rate reduction `+0.0238`. The control had one `schema_invalid` occurrence.
Stage B was not authorized and no candidate was selected.

The original aggregate used unequal valid-output denominators because the
control had one missing output. The follow-up erratum derives 23 common valid
case executions and confirms the semantic regression; it does not overwrite
the historical Stage A report.

## Testing

* **Test Files:** `apps/api/tests/test_openai_responses_gateway.py`, `scripts/tests/test_sprint12_phase_f_contract.py`
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest apps/api/tests -q`

## Additional Notes

Evidence is runtime-backed owner-delegated AI evaluation, not human evidence.
Cost accounting remains unavailable because provider price configuration is not
bound. Validation, candidate freeze, and held-out evaluation remain locked.
