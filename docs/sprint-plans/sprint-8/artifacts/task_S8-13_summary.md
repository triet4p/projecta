# Task Summary: Application API startup fail-closed validation

**Sprint:** Sprint 8
**Task:** S8-13

## Summary of Work

Added finite, side-effect-free startup validation and attached it to the API
readiness boundary. Liveness remains available for diagnostics, while readiness
returns `503` with safe configuration reason codes when trusted context,
experience project/actor scope, secret-store material, provider bootstrap, or
Semantic Core configuration is invalid. Removed `local-project` and
`local-user` authority defaults from Settings and Compose interpolation.

## Files Modified

* [startup.py](../../../../apps/api/src/projecta_api/startup.py) - Safe configuration validation and finite reason codes.
* [config.py](../../../../apps/api/src/projecta_api/config.py) - Remove fixed experience project/actor defaults.
* [context.py](../../../../apps/api/src/projecta_api/context.py) - Guard missing experience scope values.
* [main.py](../../../../apps/api/src/projecta_api/main.py) - Store validation result and fail readiness closed.
* [compose.yaml](../../../../compose.yaml) - Remove authority-bearing local project/actor defaults.
* [test_startup.py](../../../../apps/api/tests/test_startup.py), [test_main.py](../../../../apps/api/tests/test_main.py) - Startup/readiness regression coverage.

## Testing

* **Test File:** `apps/api/tests/test_startup.py`, `apps/api/tests/test_main.py`, `apps/api/tests/test_interactive_configuration.py`
* **Status:** Passed.
* **Execution Command:** `uv run pytest -q tests/test_startup.py tests/test_main.py tests/test_interactive_configuration.py`

## Additional Notes

`docker compose config --quiet` cannot run without the already-required
deployment secret variables; this is intentional fail-closed behavior. The
Compose topology was not started or mutated by this task.
