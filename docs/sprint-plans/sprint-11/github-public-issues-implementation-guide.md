# GitHub Public Issues Connector — Implementation Guide

Status: `PLANNED`

Applies to: Sprint 11 G1 amendment for `v0.6.0`

## Outcome

Implement a credential-free, read-only connector for issues and issue comments
from one exact public GitHub repository. Reuse the existing connector kernel,
evidence lifecycle, authorization policy, audit seam, and release limits. Do not
turn provider metadata into domain truth and do not change the ontology unless
the governed reuse audit rejects `NO_ONTOLOGY_CHANGE_REQUIRED`.

## Non-Goals

- No token, GitHub App, OAuth, private repository, organization discovery, or
  configurable API host.
- No pull requests, reviews, discussions, projects, notifications, webhooks, or
  continuous polling.
- No provider writes and no automatic Person/Organization identity merge.
- No removal of the Teams implementation, Keycloak, OpenBao, or recovery gates.
- No claim that unauthenticated public access validates an authenticated
  enterprise connector.

## Existing Seams to Reuse

| Seam | Implementation direction |
| --- | --- |
| `connectors/contracts.py` | Add the finite connector type and typed internal installation configuration; keep v1 limits and canonical event contract. |
| `connectors/registry.py` | Register one descriptor and adapter; do not branch orchestration by provider. |
| `connectors/orchestration.py` | Reuse authorization, run lease, immutable config snapshot, event validation, evidence commit, semantic lifecycle, and cursor commit ordering. |
| `connectors/public_api.py` | Add finite catalog/setup/status projections; never accept `providerConfig` or arbitrary URLs in the public DTO. |
| `connectors/installation_service.py` | Reuse project capability, revision, idempotency, and audit checks for create/update/revoke. |
| `connectors/event_validation.py` | Preserve event/count/byte/deadline enforcement before evidence commit. |
| `connectors/source_mapping.py` | Reuse source/evidence/candidate mapping and treat GitHub actors as non-authoritative hints. |
| `main.py` composition | Compose the HTTP transport and register the adapter without making provider availability a startup dependency. |
| `ConnectionsScreen.tsx` | Add credential-free repository setup and truthful experimental Teams labeling using generated types. |

Create `apps/api/src/projecta_api/connectors/github_public_issues.py` for the
provider-specific configuration, transport, pagination validation, mapping, and
cursor codec. Split the HTTP transport into a second module only if the file
exceeds the repository's normal reviewable size.

## Installation Contract

Use the exact connector type `github-public-issues`. The internal configuration
contains only:

```text
owner: validated repository owner
repository: validated repository name
contractVersion: connector-contract.v1
capabilities: [read:issues, read:issue-comments]
limits: existing Sprint 10/11 limits
```

The browser must not send an internal `providerConfig`. Add a typed setup route
that accepts only bounded `owner` and `repository` fields after
`connector-admin` authorization, validates them, and issues a short-lived,
single-use opaque setup handle. Installation creation consumes the handle into
the server-owned capability snapshot. This follows the existing Teams setup
boundary without inventing a secret: the handle protects configuration and
revision flow, not credentials.

Validation rules:

- Normalize surrounding whitespace once; preserve GitHub-visible casing for
  display but use a canonical lowercase comparison key.
- Reject empty values, path separators, dot segments, percent encoding,
  control characters, query/fragment characters, and values above the chosen
  documented bound.
- Never accept a full repository URL, API URL, hostname, organization wildcard,
  or repository search expression.
- Probe repository visibility only from the server. Return a finite safe
  `not-found-or-unavailable` result without exposing cross-project state.

## HTTP and Pagination Contract

Use a small async HTTP transport with redirects and automatic retries disabled.
Send a fixed `User-Agent`, `Accept: application/vnd.github+json`, and the pinned
GitHub REST API version header. The only initial requests are:

```text
GET /repos/{owner}/{repository}/issues
  ?state=all&sort=updated&direction=asc&since={issue-watermark}&per_page=100

GET /repos/{owner}/{repository}/issues/comments
  ?sort=updated&direction=asc&since={comment-watermark}&per_page=100
```

Exclude any issue object containing a `pull_request` member. A comment is kept
only when its `issue_url` resolves to the same bound repository and its parent
is an issue rather than a pull request. If parent classification cannot be
proved within the fixed request budget, omit the event and return `truncated`
instead of guessing.

Follow a `Link` target only when all of these hold:

- scheme is `https`, host is exactly `api.github.com`, no userinfo or fragment;
- path remains inside the bound repository's issue or issue-comment endpoint;
- query keys and values remain in the adapter allowlist;
- the absolute deadline, event count, byte limits, and fixed page/request budget
  remain available.

Stop with `truncated` when any page, request, event, byte, or deadline bound is
reached. Do not sleep, retry, or advance the cursor on a failed/truncated run.

## Canonical Event Mapping

Map issue and comment observations independently:

| Field | Issue | Issue comment |
| --- | --- | --- |
| `eventType` | `source.created` when provider timestamps match; otherwise `source.updated` | Same rule |
| `occurredAt` | Provider `updated_at` | Provider `updated_at` |
| `contentType` | `application/json` | `application/json` |
| Evidence content | Deterministic bounded projection of title, body, state, and safe label names | Deterministic bounded projection of body and parent issue number |
| Actor hint | Bounded login plus provider user ID as an untrusted hint | Same |
| External reference | Internal opaque hash derived from installation scope, resource kind, provider ID, and provider revision | Same |

Serialize the evidence projection with canonical JSON: stable key order, UTF-8,
no insignificant whitespace, no raw response envelope, no HTML rendering, and
no provider URL/user object. Preserve only fields required for review and
idempotent evidence.

Because canonical-event v1 treats the same event ID with changed bytes as a
conflict, derive the event ID from a domain-separated SHA-256 digest of
installation scope, resource kind, provider numeric ID, and `updated_at`.
Different revisions become distinct immutable observations; replay of the same
revision produces the same ID and bytes. Use a fixed prefix and bounded digest
encoding, never the raw provider ID in public projections.

Provider deletions are not observable through this unauthenticated polling
slice and must not be synthesized. Closing/reopening an issue is an update
observation, not deletion.

## Cursor Semantics

Encode an opaque, versioned, base64url canonical-JSON cursor no larger than the
existing contract limit. It holds independent issue and comment watermarks:

```text
version
issue:   (updated_at, numeric_id)
comment: (updated_at, numeric_id)
```

GitHub `since` is inclusive and timestamps may tie. Request from the timestamp
watermark, sort returned observations by `(updated_at, numeric_id)`, and discard
only tuples less than or equal to the committed tuple. Validate timestamp and
integer bounds before use. The adapter proposes the greatest successfully
processed tuple for each stream; only the orchestrator commits it after durable
evidence and semantic work complete.

On a first run, use an explicit bounded lookback supplied by server policy, not
an unbounded repository-history scan. Document the chosen lookback in the
catalog/runbook and return `truncated` if the repository exceeds the run bounds.

## Failure Mapping

| Provider/transport result | Connector outcome |
| --- | --- |
| `404` | `installation-invalid` or the existing safe not-found equivalent |
| `403` with rate-limit headers exhausted, or `429` | `rate-limited` with bounded retry-after metadata only if the contract supports it |
| Other `403` | `provider-forbidden` |
| `5xx`, DNS, TLS, connection error | `provider-unavailable` |
| Absolute deadline exceeded | `timed-out` |
| Invalid JSON/schema/timestamp/identifier | `provider-output-invalid` |
| Invalid redirect or pagination link | `provider-output-invalid` security failure |
| Any run bound reached with otherwise valid data | `truncated` |

Use the existing finite enums where names differ; do not add an ad hoc public
error string. Provider response bodies and headers outside an explicit safe
allowlist never cross the adapter.

## Security and Privacy Checklist

- Fixed host and constructed paths eliminate arbitrary-URL SSRF; still test DNS,
  redirect, userinfo, encoded path, and malicious `Link` cases.
- Enforce bytes while streaming and before JSON/materialization where possible.
- Treat Markdown, links, labels, usernames, Unicode, and control characters as
  hostile input; render through existing safe text components only.
- Do not persist response headers, IP addresses, ETags, URLs, or complete actor
  objects unless a reviewed operational need is added.
- Keep owner/repository inside the server-owned installation snapshot. If a
  public display label is needed, expose a separately bounded safe label rather
  than an authorization identifier.
- Run the existing API/DOM/log/RDF/database/backup/artifact leak gates with
  seeded provider IDs and payload markers.
- Do not require OpenBao access for this connector run, but keep global OpenBao
  readiness and recovery acceptance unchanged.

## Tests Required Before Live Acceptance

1. Unit fixtures: issue, comment, pull-request exclusion, edit, close/reopen,
   equal timestamps, duplicate revision, empty body, malicious Markdown/HTML,
   Unicode, oversized content, malformed JSON, and invalid timestamps.
2. Pagination: valid next page, wrong host/scheme/repository/path/query,
   redirect, cycle, page cap, event cap, byte cap, and deadline.
3. Cursor/replay: first run, overlap at equal timestamp, independent streams,
   exact replay, restart, truncated run, failed run, and semantic rollback.
4. Failure mapping: `403`, exhausted rate limit, `404`, `429`, `5xx`, TLS,
   timeout, connection error, malformed headers, and invalid body.
5. Authorization/isolation: normal reviewer cannot install/update/revoke;
   cross-project/user/installation handles remain indistinguishable and safe.
6. Public contract/UI: generated types, catalog mode, credential-free setup,
   experimental Teams label, keyboard operation, narrow layout, and no raw IDs.
7. System acceptance: deterministic runner, clean Compose, restart/recovery,
   audit correlation, evidence/candidate continuity, and leak scans.

## Live Free Acceptance Procedure

The operator later creates a disposable public repository containing only
fabricated issues and comments. Use no work project, company name, customer
data, personal chat, credential, or copied production text.

1. Seed at least one issue, one comment, one edited issue, one edited comment,
   and one pull request used only to prove exclusion.
2. Install the exact repository through the credential-free setup flow.
3. Run once and verify bounded evidence, candidates, audit correlation, and
   project isolation.
4. Edit one issue/comment, rerun, and verify immutable revision plus cursor
   behavior; replay again and prove idempotency.
5. Exercise one finite provider failure or rate-limit fixture without attacking
   the live service.
6. Export only sanitized counts, hashes, timestamps, command/test versions, and
   pass/fail evidence to the G2 packet.
7. Delete or archive the disposable repository after G2 evidence is accepted.

## Recommended Implementation Order

1. Freeze provider, threat, semantic-reuse, configuration, cursor, and failure
   contracts (S11-A02 through S11-A05).
2. Implement typed config, transport, issue/comment mapping, pagination, cursor,
   and failures (S11-A06 through S11-A11).
3. Register the adapter and add setup/API/UI truthfulness (S11-A12 through
   S11-A14).
4. Add deterministic, security, and system evidence (S11-A15 through S11-A17).
5. Run the disposable public-repository journey and wire release gates
   (S11-A18 through S11-A20).

Do not start S11-A06 until the ontology reuse audit and amended security
contract are reviewed. Do not open G2 until the live evidence and all carried
Sprint 11 gates are green.
