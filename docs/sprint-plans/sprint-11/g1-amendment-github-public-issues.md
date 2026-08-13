# Sprint 11 G1 Amendment — GitHub Public Issues Release Gate

Status: `APPROVED_WITH_CONDITIONS`

Decision date: 2026-08-13

Related approval: [Sprint 11 G1 approval](g1-approval.md)

## Decision

Release `v0.6.0` with one credential-free, read-only GitHub Public Issues
connector as the canonical live-provider acceptance slice. Defer live Microsoft
Teams acceptance and any production-ready Teams claim until an explicitly
authorized sandbox tenant is available.

The connector binds one exact public GitHub repository per installation and
reads issues and issue comments through the public GitHub REST API without a
token. It does not read pull requests, private repositories, discussions,
projects, notifications, email, organization membership, or user-private data,
and it cannot create, edit, or delete provider content.

This amendment supersedes only the provider choice and live-provider release
gate in the original G1 approval. It preserves the approved Keycloak, session,
membership, authorization, OpenBao, evidence, recovery, audit, Compose, and
ontology boundaries.

## Why This Is the v0.6.0 Choice

- A synthetic public repository can be created and destroyed without an Azure
  subscription, Microsoft 365 license, tenant administrator, or provider
  consent workflow.
- Credential-free REST access exercises a real external network boundary,
  pagination, rate limiting, malformed content handling, replay, evidence, and
  cursor behavior while avoiding access to the user's work tenant.
- Issues and comments map to the released source/evidence/candidate lifecycle;
  installation, cursor, pagination, rate-limit, and provider identifiers remain
  operational state rather than ontology facts.
- The already implemented Teams adapter remains useful experimental work, but
  its deterministic tests are not evidence of live tenant authorization.

## Fixed Provider Contract

| Concern | Amended decision |
| --- | --- |
| Connector type | `github-public-issues` |
| Provider origin | Fixed `https://api.github.com`; no configurable base URL |
| Installation scope | One exact, validated `owner/repository` pair |
| Authentication | None for the v0.6.0 slice; no token field or secret reference |
| Resources | Repository issues and repository issue comments; exclude objects containing `pull_request` |
| Mutation | None |
| Execution | Explicit bounded run, single attempt, no hidden retry |
| Existing bounds | 100 events/run, 10 MiB/run, 1 MiB/event, 30-second absolute deadline |
| Pagination | Validate `Link` targets; follow only allowlisted API paths for the bound repository; stop truthfully as `truncated` when any bound is reached |
| Cursor | Adapter-owned opaque cursor with independent issue and comment watermarks; commit only after the orchestrator durably commits the run |
| Public projection | Opaque Projecta installation/run handles; no provider numeric IDs or raw payloads |
| Semantics | Reuse released source, evidence, candidate, provenance, actor-hint, and project-scope terms |

## Security Conditions

1. The transport constructs URLs from the validated repository binding. It
   rejects redirects and never accepts a browser-supplied host, URL, or `Link`
   outside `https://api.github.com/repos/{owner}/{repository}/...`.
2. Owner and repository names are validated as bounded path segments before
   persistence and are never used as authorization authority.
3. Provider content is untrusted evidence. HTML, Markdown, links, usernames,
   labels, and actor hints cannot create assertions or merge identities.
4. Rate-limit exhaustion, `403`, `404`, `429`, `5xx`, timeout, invalid JSON,
   invalid pagination links, and size violations terminate finitely without
   hidden retry or cursor advancement.
5. Logs, audit records, public DTOs, browser storage, RDF, and release artifacts
   contain neither raw provider payloads nor provider numeric identifiers.
6. OpenBao remains a required platform boundary and a tested Teams dependency;
   this credential-free connector must not weaken its readiness, recovery, or
   leak gates.

## Teams Disposition

Teams remains implemented and covered by deterministic contract/regression
tests. It is marked experimental and unavailable for the canonical `v0.6.0`
live journey. S11-67 is deliberately not completed and is excluded from G2/G3
release gating by this amendment. A future release may restore Teams as a live
gate only after a separate human authorization names a disposable tenant,
application registration, consent scope, channel, data-handling rules, and
teardown owner.

## Semantic Outcome

The working outcome remains `NO_ONTOLOGY_CHANGE_REQUIRED`, subject to the
amendment task that reruns the competency-question audit for issue/comment
evidence. If that audit finds a required graph-queryable concept, implementation
must pause and use `$projecta-evolve-ontology` with its human semantic gate.

## Approval Conditions Before G2

- The amendment tasks in the Sprint 11 plan are complete.
- Sanitized replay, failure, isolation, and live public-repository evidence are
  attached to the G2 packet.
- The catalog, UI, changelog, runbooks, and release notes describe GitHub Public
  Issues as the live connector and Teams as experimental/deferred.
- No token, private repository, work-tenant resource, or production payload is
  used for acceptance.
- The exact release candidate passes all carried identity, OpenBao, recovery,
  semantic, security, and clean-Compose gates.

## Residual Risks Accepted for v0.6.0

- Unauthenticated GitHub API capacity is intentionally small and externally
  shared; the connector must surface rate-limit exhaustion rather than retry.
- Public provider content may contain hostile Markdown, links, Unicode, or
  personal information; the synthetic acceptance repository must use fabricated
  content and the evidence boundary must retain its existing sanitization.
- Public issues do not validate authenticated private-resource access. That is
  an explicit limitation, not a substitute claim for Teams or private GitHub.
