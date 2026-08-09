# Task Summary: Compose health failure diagnostics

**Sprint:** Sprint 8
**Task:** S8-22

## Summary of Work

Separated Compose liveness and readiness semantics by making API healthchecks
probe `/health/ready`, while retaining `/health/live` for process diagnostics.
Added explicit start periods and a runbook that inspects Docker
`.State.Health.Log` probe exit evidence, traces dependency order, and records
finite correlated failures without secrets or payloads.

## Files Modified

* [compose.yaml](../../../../compose.yaml) - Readiness healthchecks and probe timing.
* [check_sprint8_health_contract.ps1](../../../../scripts/check_sprint8_health_contract.ps1) - Compose health contract test.
* [sprint-8-operations.md](../../../../docs/runbooks/sprint-8-operations.md) - Health/failure diagnostic runbook.

## Testing

* **Test File:** [check_sprint8_health_contract.ps1](../../../../scripts/check_sprint8_health_contract.ps1)
* **Status:** Passed.
* **Execution Command:** `./scripts/check_sprint8_health_contract.ps1`; `docker compose -f compose.yaml -f compose.dev.yaml config --quiet` with non-secret placeholder environment values.

## Additional Notes

Compose was validated but not started. Required deployment secrets remain
required; placeholder values were used only for static interpolation validation.
