# GitHub Public Issues Provider Contract — Sprint 11 S11-A03

**Status:** `CONTRACT_FROZEN_FOR_S11_IMPLEMENTATION`

**Task:** S11-A03

**Contract:** `github-public-issues.v1` over `connector-contract.v1`

## Provider boundary

The adapter performs one unauthenticated, read-only attempt against the fixed
origin `https://api.github.com`. It must not receive a token and must not accept
an API origin, repository URL, redirect target, or arbitrary provider path from
the browser or installation payload.

Every request sends:

```text
Accept: application/vnd.github+json
User-Agent: Projecta/<bounded-version>
X-GitHub-Api-Version: 2026-03-10
```

The selected API version is the current supported GitHub REST version checked
on 2026-08-13. A later version change is a reviewed contract update, not a
runtime-discovered setting.

## Installation and validation

The internal installation snapshot contains only the validated owner,
repository, connector contract version, capabilities, and server limits:

```text
owner: validated owner segment
repository: validated repository segment
contractVersion: connector-contract.v1
capabilities: [read:issues, read:issue-comments]
```

Validation normalizes surrounding whitespace once, preserves provider casing
for display, and uses lowercase owner/repository keys for comparisons. Owner
and repository are bounded path segments; empty values, `/`, `\\`, control
characters, percent escapes, query/fragment characters, exact `.`/`..` segments,
full URLs, hostnames, wildcards, and search expressions are rejected. The
server may perform a separate fixed-origin repository visibility probe during
setup and returns only `not-found-or-unavailable` to an unauthorized or
ambiguous caller.

## Sync endpoints

The only initial sync requests are:

```text
GET /repos/{owner}/{repository}/issues
  ?state=all&sort=updated&direction=asc&since={issue-watermark}&per_page=100

GET /repos/{owner}/{repository}/issues/comments
  ?sort=updated&direction=asc&since={comment-watermark}&per_page=100
```

`since` is an RFC 3339 UTC timestamp. It is inclusive at the provider and is
paired with local `(updated_at, numeric_id)` filtering to resolve equal-time
overlap safely.

The issues response is a JSON array of bounded objects. Any object with a
`pull_request` member is excluded. A comment is accepted only when its
`issue_url` is a URL for the same bound repository and its parent is proven to
be an issue, not a pull request. If parent classification cannot be proven
within the request budget, the adapter omits the observation and returns
`truncated` rather than guessing.

## Pagination allowlist

Only a `Link` header relation `rel="next"` may advance traversal. A next link
is followed only if:

- scheme is exactly `https`;
- host is exactly `api.github.com`, with no userinfo or fragment;
- path is exactly the bound issues or issue-comments endpoint;
- owner/repository path segments match the installation after canonical
  comparison;
- query keys are limited to the endpoint's `state`, `sort`, `direction`,
  `since`, `per_page`, and `page` parameters;
- `per_page` is at most 100 and the link does not change the stream contract;
- the link has not already been visited and all count, byte, request, and
  deadline budgets remain available.

`prev`, `first`, and `last` are not followed. Invalid, cyclic, duplicated,
cross-repository, or out-of-budget links produce `provider-output-invalid` or
`truncated` as specified below. Redirects are disabled at the HTTP transport;
an HTTP redirect is a provider-output security failure.

## Canonical event mapping

Issue and issue-comment observations map independently to `canonical-event.v1`:

| Field | Issue | Issue comment |
| --- | --- | --- |
| `eventType` | `source.created` when the provider revision is first observed; otherwise `source.updated` | Same rule |
| `occurredAt` | `updated_at` | `updated_at` |
| `contentType` | `application/json` | `application/json` |
| Evidence projection | bounded title, body, state, and safe label names | bounded body and parent issue number |
| Actor hint | bounded login and numeric user ID, non-authoritative | Same |
| External reference | opaque installation-scoped digest | opaque installation-scoped digest |

Evidence is canonical JSON with sorted keys, UTF-8, no insignificant
whitespace, no HTML rendering, no raw response envelope, no provider URL, and
no complete user object. The event ID is a domain-separated SHA-256 digest of
installation scope, resource kind, provider numeric ID, and `updated_at`. The
raw provider ID never appears in public projections.

Provider deletion is not synthesized. Closing/reopening an issue is an update
observation. A changed revision has a new immutable event ID; the same revision
has the same event ID and canonical bytes.

## Cursor and commit ordering

The cursor is an opaque versioned base64url canonical-JSON value no larger than
the existing contract limit:

```text
version
issue:   (updated_at, numeric_id)
comment: (updated_at, numeric_id)
```

The adapter proposes the greatest successfully processed tuple per stream.
`ConnectorSyncOrchestrator` commits the cursor only after evidence and semantic
work are durable. Failed, cancelled, or truncated runs do not advance either
watermark.

## Bounds and retry policy

The adapter inherits 100 events/run, 10 MiB/run, 1 MiB/event, and a 30-second
absolute deadline. It additionally enforces at most 20 provider requests per
run and 10 pages per stream. It performs no automatic retry, backoff, sleep,
redirect follow, or hidden second attempt. A user-triggered retry is a new
authorized run and idempotency operation.

## Failure mapping

| Provider/transport condition | Finite connector outcome | Cursor |
| --- | --- | --- |
| `404`, or setup visibility ambiguity | `installation-invalid` / safe `not-found-or-unavailable` | Unchanged |
| `403` with exhausted rate headers, or `429` | `rate-limited` | Unchanged |
| Other `403` | `provider-forbidden` | Unchanged |
| `5xx`, DNS, TLS, connection failure | `provider-unavailable` | Unchanged |
| Absolute deadline/cancellation | `timed-out` / existing cancellation outcome | Unchanged |
| Invalid JSON, schema, timestamp, identifier, or header | `provider-output-invalid` | Unchanged |
| Invalid redirect or unsafe pagination link | `provider-output-invalid` | Unchanged |
| Valid data reaches count/byte/page/request/deadline bound | `truncated` | Unchanged |

Only safe status/outcome metadata and bounded retry-after information, when
supported by the existing public taxonomy, may cross the adapter boundary.
Provider response bodies, arbitrary headers, URLs, IP addresses, ETags, and
complete actor objects never cross it.

## Compatibility rules

The adapter must use existing `ConnectorPolicy`,
`ConnectorSyncOrchestrator`, canonical-event validation, evidence storage,
source mapping, and PostgreSQL repository contracts. It must not add a
provider-specific orchestration branch, ontology term, public raw provider
field, or secret dependency.

## Official references checked 2026-08-13

- [List repository issues](https://docs.github.com/en/rest/issues/issues)
- [List issue comments for a repository](https://docs.github.com/en/rest/issues/comments)
- [Using pagination in the REST API](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)
- [API versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions)
- [Rate limits for the REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
