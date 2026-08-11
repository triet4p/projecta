# Task Summary: S10-03 — Define the canonical event contract

**Sprint:** Sprint 10 — Governed Connector Foundation and v0.5.0

**Task:** S10-03

## Summary of Work

Defined the `canonical-event.v1` internal envelope, including the server-bound
event identity tuple, project/installation scope, actor hint, external
reference, event type, evidence reference/hash metadata, canonical body hash,
serialization rules, validation order, bounded defaults, and safe typed problem
codes. The contract explicitly prevents domain assertions, raw payload leakage,
provider-shaped fields, hidden retries, and cross-project scope widening.

## Files Modified

* [docs/architecture/canonical-event-contract.md](F:/ai-ml/projecta/docs/architecture/canonical-event-contract.md) — Canonical event and idempotency contract.
* [scripts/tests/test_sprint10_canonical_event_contract.py](F:/ai-ml/projecta/scripts/tests/test_sprint10_canonical_event_contract.py) — Deterministic contract-presence and guardrail test.
* [docs/sprint-plans/sprint-10/artifacts/task_S10-03_summary.md](F:/ai-ml/projecta/docs/sprint-plans/sprint-10/artifacts/task_S10-03_summary.md) — Task traceability record.

## Testing

* **Test File:** [scripts/tests/test_sprint10_canonical_event_contract.py](F:/ai-ml/projecta/scripts/tests/test_sprint10_canonical_event_contract.py)
* **Status:** Passed.
* **Execution Command:** `uv run --no-project python -m unittest discover -s scripts/tests -p "test_sprint10_canonical_event_contract.py"`; `git diff --check`

## Additional Notes

Event-type allowlists and numeric limits are proposed contract defaults and
remain subject to G1 approval. The contract intentionally leaves provider
fields in raw evidence and does not add ontology vocabulary.
