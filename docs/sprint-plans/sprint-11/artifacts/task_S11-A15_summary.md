# Task Summary: S11-A15 — Add Sanitized Deterministic Fixtures and Contract Tests

## Outcome

Added sanitized, fabricated GitHub Public Issues fixtures for issues, pull
request exclusion, comments, and malformed provider output. Added adapter
contract coverage for both provider streams, deterministic mapping, bounded
cursor emission, source mapping reuse, and malformed-output normalization.

The fixtures contain no work-tenant, customer, credential, or production data.

## Evidence

- GitHub mapping/setup/transport, public API, source mapping, and kernel
  regression subset: 37 passed.
- Ruff, Pyright, and `git diff --check`: pass.

## Status

`DONE`
