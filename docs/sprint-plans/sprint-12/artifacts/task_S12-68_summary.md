# S12-68 — Run the v0.6.0 baseline

The released `v0.6.0` runtime was executed on all 160 development/validation
cases with one bounded attempt per case. The report is
`RUNTIME_BACKED_WITH_FAILURES`: 105 cases produced valid normalized output and
55 were fail-closed as missing output (`48 invalid_evidence`, `7
schema_invalid`). The task is complete as an execution record, but the G4
quality gate remains failed because schema validity is not satisfied.

## Testing

The self-test covers missing configuration and the no-network bounded adapter;
the runtime report binds all 160 case IDs, configuration and manifest digests.
