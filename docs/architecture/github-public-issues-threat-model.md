# GitHub Public Issues Connector Threat Model — Sprint 11 S11-A04

**Status:** `CONTRACT_FROZEN_FOR_S11_IMPLEMENTATION`

**Task:** S11-A04

The provider is public but untrusted. Public visibility removes the need for a
provider credential; it does not remove SSRF, hostile-content, availability,
privacy, integrity, or project-isolation risk.

## Threat/control matrix

| ID | Threat | Required control and evidence |
| --- | --- | --- |
| GH-01 | Arbitrary-URL SSRF through owner/repository or setup input | Accept path segments only; fixed `https://api.github.com`; reject URLs, hosts, escapes, separators, and controls; negative validation tests |
| GH-02 | Redirect reaches another host or scheme | Disable redirects; reject any redirect response; transport test proves one fixed origin |
| GH-03 | Malicious `Link` header causes traversal | Parse only `rel="next"`; validate scheme, host, bound path, query allowlist, cycle, and budget before every follow |
| GH-04 | Repository confusion via casing, encoded paths, or alternate endpoint | Canonical lowercase comparison key, exact bound endpoint, no percent encoding or alternate path, same-repository fixtures |
| GH-05 | Pull request imported as issue | Exclude every issue object containing `pull_request`; prove comments have an issue parent in the bound repository |
| GH-06 | Malicious Markdown, HTML, Unicode, or control characters | Strict schema validation, bounded canonical projection, no HTML rendering, safe existing UI text components, DOM/log/RDF leak tests |
| GH-07 | Oversized body/label/actor/payload | Stream and enforce 1 MiB/event, cumulative 10 MiB raw response bytes/run, 100 events, nesting/field/string limits, and 30-second deadline before durable commit |
| GH-08 | Rate exhaustion or secondary throttling amplifies load | Read safe rate headers, map `403`/`429` to `rate-limited`, no sleep/backoff/hidden retry, no cursor movement |
| GH-09 | Provider outage or slow connection hangs the run | Fixed absolute deadline, bounded request count, cancellation, finite `provider-unavailable`/`timed-out` outcomes |
| GH-10 | Malformed JSON, timestamp, identifier, or header | Strict typed parser and canonicalization; fail closed as `provider-output-invalid`; no evidence/cursor commit |
| GH-11 | Same revision is duplicated or changed bytes collide | Domain-separated revision-aware event ID, canonical body hash, existing inbox conflict/replay semantics |
| GH-12 | Failed/truncated import advances cursor | Adapter proposes cursor only; orchestrator commits after durable evidence and semantic work; rollback tests |
| GH-13 | Provider IDs or URLs leak to browser, logs, RDF, DB, backup, or evidence | Opaque references and safe projections; allowlist metadata; seeded marker leak scans across all artifacts |
| GH-14 | GitHub login is treated as Projecta identity | Actor is a bounded non-authoritative hint; no automatic `Person` merge; identity regression fixture |
| GH-15 | Cross-project installation or handle confusion | Server-derived project/installation scope, capability checks, opaque indistinguishable failures, concurrent cross-project tests |
| GH-16 | Public data exposes sensitive project context | No work tenant/company/customer data in live acceptance; disposable fabricated repository; sanitized evidence archive/delete procedure |
| GH-17 | Provider writes or side effects occur accidentally | Read-only endpoint allowlist and method allowlist; no token, write route, webhook, or background scheduler |
| GH-18 | Setup handle is replayed or misbound | Short-lived single-use server handle bound to actor/project/revision; consume atomically and audit safely |
| GH-19 | Pagination cycle or page explosion causes denial of service | Visited-link set across the run, 20-request total/10-page-stream caps, cumulative event/raw-byte/deadline caps, explicit `truncated` outcome with no cursor advancement |
| GH-20 | Hidden dependency on OpenBao or work tenant | Connector has no provider secret reference; global OpenBao/recovery gates remain unchanged; no Entra/work-tenant calls |

## Trust boundaries

```text
Projecta browser
  → typed Application API and ConnectorPolicy
  → server-owned installation/setup handle
  → fixed GitHub HTTPS transport
  → canonical event and bounded evidence
  → existing source/candidate/provenance lifecycle
  → PostgreSQL operational state and project-scoped semantic graphs
```

The browser never submits project authority, provider configuration, token,
cursor, canonical envelope, or raw provider payload. The adapter never writes
asserted RDF or decides identity, project membership, or authorization.

## Required negative evidence before implementation is accepted

Deterministic fixtures must cover unsafe owner/repository values, wrong-host and
wrong-scheme redirects, userinfo, encoded paths, wrong-repository and malformed
`Link` values, pagination cycles, pull requests, parent ambiguity, hostile
Markdown/HTML/Unicode/control characters, oversized content, invalid JSON and
timestamps, rate exhaustion, `403`, `404`, `429`, `5xx`, TLS/DNS/connection
failure, timeout, cancellation, failed/truncated rollback, duplicate/edit
replay, cross-project handle use, raw-ID leakage, and no-token/no-write
behavior.

Live acceptance must use only fabricated data in a disposable public repository.
It must retain sanitized counts, hashes, timestamps, versions, and pass/fail
results, then archive or delete the repository after G2 evidence is accepted.

## Residual risks

- Unauthenticated GitHub REST requests share an IP-based primary limit of 60
  requests per hour and may encounter secondary limits; the connector therefore
  treats provider capacity as external and bounded.
- Provider deletion history is not observable in this polling slice; deletion
  must not be synthesized.
- Public content can still contain personal or sensitive text; the disposable
  repository and sanitization procedure are mandatory, not optional.
- GitHub API versions and endpoint behavior can change; the pinned version and
  official-document recheck are release-gate inputs.

## Official references checked 2026-08-13

- [GitHub REST API versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions)
- [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub REST issues](https://docs.github.com/en/rest/issues/issues)
- [GitHub REST issue comments](https://docs.github.com/en/rest/issues/comments)
