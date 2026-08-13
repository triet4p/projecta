# Task Summary: S11-14 — Approve G1 With Revisions

**Sprint:** Sprint 11

**Task:** S11-14

## Summary of Work

Recorded the human G1 outcome as `APPROVED_WITH_REVISIONS`. The approved
baseline selects Keycloak 26.7.0, OpenBao 2.6.1, certificate-based app-only
Teams access with `ChannelMessage.Read.Group`, additive operator-seeded
membership, session invalidation after restore, and
`NO_ONTOLOGY_CHANGE_REQUIRED`. The identity protocol surface is separated
from private management surfaces, and OpenBao is explicitly documented as a
service-level custody boundary while Projecta retains exact authorization.

## Files Modified

* [g1-approval.md](../g1-approval.md) - Complete G1 approval record and revisions.
* [phase-a-review-packet.md](../phase-a-review-packet.md) - Approval status and implementation authorization.
* [sprint-11.md](../../sprint-11.md) - Marked S11-14 complete; S11-15 remains pending.
* [decisions.md](../../../../.agents/memory/decisions.md) - Append-only durable architecture decision.

## Testing

* **Test File:** [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py)
* **Status:** Passed previously; decision record and status invariants rechecked with `git diff --check`.
* **Execution Command:** `git diff --check`

## Additional Notes

Image digests are intentionally not invented here. S11-15 must resolve and
record immutable digests after pulling the approved image tags. G1 approval
does not imply HA, unattended cold restart, G2, G3, or release authorization.
