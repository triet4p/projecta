# Sprint 12 G5 Optimization Packet v15

> Historical gate snapshot. The authoritative current packet is
> [G5 Optimization Packet v17](g5-optimization.v17.md).

**Status:** `G5_F12_CLOSED_REJECTED_OFFLINE_REMEDIATION_PREPARATION_ONLY`

This packet captured the closed-rejected/offline-preparation state. It and
earlier packets remain immutable historical evidence.

## Owner decision

S12-RM-27 closes f12 as `COMPLETED_REJECTED_NO_STAGE_B`. The immutable Stage A
report failed hard gates with six schema-invalid responses and 17
invalid-evidence findings, and it also failed registered threshold and slice
gates. The passing gold-relations control does not override candidate failures.

The spent RM-25 authorization cannot be reused. No Stage B, candidate
selection, validation or held-out access is authorized.

## Bound evidence

- Owner decision:
  `evaluation/sprint-12/optimization/s12-f-12-stage-a-decision.v1.json`
- Decision transition:
  `evaluation/sprint-12/optimization/s12-f-12-rm27-decision-transition.v1.json`
- Immutable report:
  `evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json`
- Machine packet: `evaluation/sprint-12/optimization/g5-packet.v15.json`

## Next permitted work

Only offline preparation of a schema/evidence remediation is open. A future
provider run requires a superseding preregistration, execution package,
technical freeze, exact-commit review and new owner authorization.
