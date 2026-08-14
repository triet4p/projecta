# S12-86 — Blinded test run

Implemented a blinded-run guard that requires preregistration, verified custody
and a frozen candidate. No held-out run was executed.

## Testing

Missing preregistration produces `BLINDED_RUN_BLOCKED` with zero outputs.
