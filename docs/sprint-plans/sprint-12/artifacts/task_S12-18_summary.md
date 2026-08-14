# Task Summary: S12-18 — Define Annotator Qualifications

**Sprint:** Sprint 12

**Task:** S12-18

## Summary of Work

Defined the required language and BrSE/project-domain competence, annotation
training, independence, conflict disclosure, rule-based disagreement records
and third-reviewer adjudication authority.

## Files Modified

* [annotation-guide.v1.md](../../../../evaluation/sprint-12/annotation-guide.v1.md) - Qualification-relevant labeling contract.
* [data-governance.v1.md](../../../../evaluation/sprint-12/data-governance.v1.md) - Provenance and custody controls.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Annotation and adjudication contract.
* [sprint-12.md](../../sprint-12.md) - Marked S12-18 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Missing qualified language coverage must reduce the affected slice explicitly,
not weaken the labeling standard.
