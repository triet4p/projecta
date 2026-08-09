# Task Summary: Cross-boundary failure-injection matrix

**Sprint:** Sprint 8
**Task:** S8-25

## Summary of Work

Added a deterministic failure-injection matrix spanning the API provider and
Semantic Core boundaries, Semantic Core/Fuseki query handling, and the Nginx
upstream contract. Provider timeout, rate limit, and schema failures now prove
one correlated terminal problem and zero Semantic Core ingestion calls. API
crashes are converted to a sanitized correlated `INTERNAL_ERROR`; Semantic
Core 4xx/5xx and invalid-success responses remain one terminal downstream
problem. Fuseki unavailable and invalid query responses are covered without an
update mutation, and the Nginx proxy budget/log contract is included in the
runner.

## Files Modified

* [main.py](../../../../apps/api/src/projecta_api/main.py) - Sanitized catch-all
  terminal error with request/operation correlation.
* [test_sprint8_failure_injection.py](../../../../apps/api/tests/test_sprint8_failure_injection.py)
  - API provider, crash, Semantic Core 4xx/5xx, invalid-response, and mutation
    assertions.
* [FusekiGatewayTest.java](../../../../services/semantic-core/src/test/java/org/projecta/semanticcore/FusekiGatewayTest.java)
  - Unavailable/invalid Fuseki injection and no-update assertion.
* [projections.py](../../../../apps/api/src/projecta_api/projections.py) -
  Backward-compatible `sourceText`/`evidenceText` aliases with numeric offsets.
* [compose.yaml](../../../../compose.yaml) and [pyproject.toml](../../../../apps/api/pyproject.toml)
  - Exclude repository-source-only local contract checks from container API
    acceptance while retaining them in local full pytest.
* [run_sprint8_failure_injection.ps1](../../../../scripts/run_sprint8_failure_injection.ps1)
  - Repeatable API, Java, and Nginx failure-matrix runner; `-RunCompose` also
    invokes the canonical container smoke harness.

## Testing

* **Status:** Passed.
* **Execution Commands:**
  `powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_sprint8_failure_injection.ps1`; `mvn --batch-mode verify`
* **Result:** API matrix 7 passed; API lint passed; Fuseki matrix 3 passed;
  Nginx contract passed; full Semantic Core verify passed (43 tests, 7
  skipped, Spotless clean). The optional Compose harness also passed with 100
  container API tests and 2 explicitly deselected `local_contract` tests;
  temporary network/volume cleanup completed.

## Additional Notes

The default runner is deterministic and does not require Docker. The
`-RunCompose` flag executes the existing Compose system harness when a real
cross-container environment is available; this run used process-local
temporary test secrets and no production data.
