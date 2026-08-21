# Task Summary: S12-RM-28 — Prepare Offline f12 Schema/Evidence Remediation

**Sprint:** Sprint 12
**Task:** S12-RM-28

## Summary of Work

Analyzed the immutable sanitized f12 Stage A report and repository-visible
offline contracts without provider calls, retries, held-out access or history
mutation. The analysis deterministically locates all six schema-invalid
responses: five predicted-entity Stage 1 responses and one gold-entity Stage 2
response. It also isolates all 17 invalid-evidence findings as `unsupported`
despite semantic `exactMatch` and resolved endpoint accounting. The
gold-relations control has zero materializer failures.

Because the report stores only response digests and sanitized counters, exact
malformed fields, validation paths and sole provider/prompt causality remain
unknown and are not guessed.

## Files Modified

* `scripts/s12_f12_rm28_offline_diagnostics.py` — deterministic report-only analyzer.
* `scripts/tests/test_sprint12_f12_rm28_offline_remediation.py` — digest, finding, contract and materializer reproduction tests.
* `evaluation/sprint-12/optimization/s12-f-12-rm28-diagnostic-contract.v1.json` — finite sanitized schema/evidence diagnostic contract.
* `evaluation/sprint-12/optimization/s12-f-12-rm28-offline-remediation.v1.json` — superseding offline preparation package.
* `evaluation/sprint-12/current-state-next.v1.json` and `g5-packet.v16.offline-remediation-preparation.json` — explicitly non-authoritative next-state snapshots.
* Sprint 12 checklist, current-state, G5 and handoff docs — RM-28 completion and owner-review boundary.

## Testing

* **Targeted tests:** `4 passed` with one environment-only Pytest cache warning.
* **Offline reproductions:** strict stage envelopes reject unbound fields and
  unknown candidate endpoints; an exact semantic relation with a mismatched
  trigger quote is classified as unsupported.
* **Safety:** report digest remains
  `sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`;
  accounting remains 144 calls and 0 retries; no provider execution occurred.
* **Governance:** provider execution, preregistration, freeze, authorization,
  validation, held-out, Stage B, selection and promotion remain false.

## Next Gate

Owner review of the RM-28 offline remediation package. Approval is required
before any superseding preregistration/package/freeze or provider execution.
RM-28 makes no quality-improvement claim and does not authorize a rerun.
