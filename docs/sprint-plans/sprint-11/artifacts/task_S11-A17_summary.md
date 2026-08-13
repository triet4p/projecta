# Task Summary: S11-A17 — Add Credential-Free Live Acceptance Runner

## Outcome

Added `scripts/run_sprint11_github_public_issues_acceptance.ps1` for the later
disposable-public-repository journey. It accepts only the Projecta API URL,
opaque project/setup handles, bounded owner/repository inputs, and an evidence
path. It has no token parameter, never sends an `Authorization` header, does
not call GitHub write APIs, and writes only repository hash, bounded states,
counts, revisions, and sanitized failure status.

The runner creates/enables/runs/disables one GitHub installation and exits with
the native failure status. Its first run must be `succeeded` with a positive
exact provider count; `empty`, `truncated`, and `replayed` fail acceptance. It
also queries project-scoped candidate and graph evidence continuity, PR
exclusion, and forged-project isolation. A separate edit-journey producer
records edit/replay provenance without accepting a provider credential.

## Evidence

- Acceptance runner contract and Phase-F script contract: 10 passed.
- PowerShell parser: pass.
- No work-tenant, credential, provider payload, or production data used.

## Status

`DONE`
