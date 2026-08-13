# Task Summary: S11-A03 — Define the GitHub Public Issues Provider Contract

**Sprint:** Sprint 11

**Task:** S11-A03

## Summary of Work

Froze the fixed `api.github.com` origin, current REST API version header,
unauthenticated endpoints, bounded repository validation, `Link` pagination
allowlist, pull-request/parent proof rules, canonical event mapping, cursor
commit ordering, no-hidden-retry policy, and finite provider failure mapping.

## Files Modified

* [github-public-issues-provider-contract.md](../../../architecture/github-public-issues-provider-contract.md) - Provider contract.

## Validation

Official GitHub REST issues, issue comments, pagination, API-version, and
rate-limit documentation was checked on 2026-08-13. No runtime code was changed.
