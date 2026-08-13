# Task Summary: S11-A04 — Extend the GitHub Public Issues Threat Model

**Sprint:** Sprint 11

**Task:** S11-A04

## Summary of Work

Added controls and required negative evidence for SSRF, redirects, malicious
pagination, repository confusion, pull-request exclusion, hostile content,
resource exhaustion, rate limits, malformed output, replay/rollback,
cross-project isolation, external-identifier privacy, no-write behavior, and
the no-token/no-work-tenant boundary.

## Files Modified

* [github-public-issues-threat-model.md](../../../architecture/github-public-issues-threat-model.md) - Threat/control matrix.

## Validation

The threat model preserves the existing connector and OpenBao/recovery
boundaries. No runtime code was changed.
