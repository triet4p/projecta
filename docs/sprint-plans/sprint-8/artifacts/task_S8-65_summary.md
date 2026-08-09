# Task Summary: S8-65 — Clean Compose acceptance

**Sprint:** Sprint 8
**Task:** S8-65
**Status:** Complete

## Outcome

Added `scripts/run_sprint8_acceptance.ps1` with a safe preflight and an
explicit clean-volume runtime mode. It validates Compose interpolation,
readiness/liveness health contracts, rejects authority-bearing local defaults,
starts the production web image, checks restart persistence, and scans
correlated Compose logs for secret/provider/RDF leakage. Runtime cleanup uses a
unique Compose project and removes only that project's volumes unless
`-KeepStack` is explicitly requested.

The acceptance profile injects an explicit two-project fixture into clean
Fuseki volumes; canonical Compose remains unseeded when that acceptance-only
setting is absent. The run also verifies that bootstrap logs do not expose RDF
graph IRIs.

## Validation

- `scripts/check_sprint8_health_contract.ps1` — passed.
- `docker compose --profile web config` — executed by the acceptance preflight
  with validation-only secrets and an explicit two-project catalog.
- `scripts/run_sprint8_acceptance.ps1 -RunCompose` — passed from clean volumes:
  production build/startup, health, safe-log scan, API/web restart, and
  persistence checks.
- Production UI smoke on that stack passed for catalog, project selection,
  Overview, Graph, and Structured Note composer with no browser console errors.
