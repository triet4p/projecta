# Task Summary: S3-18 — Build the canonical system-test entry point

**Sprint:** Sprint 3
**Task:** S3-18

## Summary of Work

Added the `semantic-core-system-test` Compose service and one PowerShell entry
point. It builds the Java test image, starts Fuseki, waits for the ontology
bootstrap, runs Maven verification, then removes all containers, network, and
the uniquely named temporary TDB2 volume in a `finally` block.

## Files Modified

- `compose.yaml`
- `scripts/run_system_tests.ps1`
- `services/semantic-core/README.md`
- `docs/sprint-plans/sprint-3.md`

## Testing

- **Status:** Passed; the isolated Compose stack completed then removed its
  `fuseki-data` volume.
- **Execution Command:** `.\scripts\run_system_tests.ps1`

## Additional Notes

- The entry point runs only the system-test service and its declared Fuseki
  dependencies, avoiding accidental startup of the long-running application
  service.
