# Teams Provider Contract — Sprint 11 S11-11

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-11

**Contract:** `teams-adapter.v1-draft`

This contract records the current official Graph shape for discovery and
implementation planning. S11-11 must re-check official documentation and
permissions immediately before implementation because provider behavior and
permissions can change.

## Provider scope

The adapter is inbound and read-only. It may call only:

- `GET /v1.0/teams/{team-id}/channels/{channel-id}/messages`;
- the bounded reply expansion/next-link path associated with an approved root
  message;
- the Microsoft identity token endpoint needed by the approved app-only
  credential flow, if that flow is selected at G1.

The HTTP host must be exactly `graph.microsoft.com` (or an explicitly reviewed
official endpoint), use HTTPS, reject redirects, and reject arbitrary URLs
from payloads or configuration.

## Least privilege

The approved application permission is
`ChannelMessage.Read.Group` as the least-privileged application permission and
it uses resource-specific consent. `ChannelMessage.Read.All` is not used in
Sprint 11. Authentication is app-only client credentials using a certificate;
the private key is stored in OpenBao. Delegated login and refresh tokens are
out of scope.

## Retrieval and bounds

- Request `$top` within the server page limit; current documentation describes
  a default page size of 20 and an upper page size of 50 for channel messages.
- Use `@odata.nextLink` only when it is an HTTPS URL on the allowlisted host,
  matches the bound team/channel/messages path, and stays within page/deadline/
  byte budgets.
- Replies may be requested through the reviewed `replies` expansion and its
  `replies@odata.nextLink`; the adapter must impose stricter Projecta bounds
  than provider maximums.
- Graph ordering is by last modified date of the reply chain, so cursor and
  edit semantics must not assume append-only creation order.
- A response body, HTML content, attachment, mention, hosted content URL, or
  display name is untrusted input. Attachments and hosted content are not
  fetched; only safe metadata may be retained.

The initial implementation retains the Sprint 10 limits: 100 events/run,
10 MiB/run, 1 MiB/event, 30-second absolute deadline, `$top=50`, one root
message page, 10 replies/root, and 50 replies total. Root plus replies never
exceed 100 events. Reaching a bound returns `truncated`, not complete success.

Each installation binds exactly one tenant, team, and channel.

## Canonical event mapping

Each accepted message/reply becomes a `canonical-event.v1` candidate with:

- stable event identity scoped by project, installation, provider resource,
  and provider event ID;
- `source.created` or `source.updated` mapping, with explicit deletion
  observation semantics if supported by the provider response;
- UTC `occurredAt`/modified timestamp validated with bounded skew rules;
- a bounded, non-authoritative actor hint;
- an evidence content reference, byte length, media type, and content hash;
- canonical body hash over the normalized bounded body;
- root/reply hierarchy kept as evidence metadata, not new ontology vocabulary.

Provider tenant/team/channel/message IDs stay inside operational state and
internal evidence metadata. Public API projections use opaque handles.

## Failure normalization

| Provider condition | Terminal outcome | Cursor/evidence behavior |
| --- | --- | --- |
| `401`/expired token | credential failure | no cursor advance |
| `403`/consent denied | permission failure | no cursor advance |
| `429` | rate-limited | no hidden retry; no cursor advance |
| timeout/cancellation | bounded timeout/cancel | commit nothing beyond safe completed transaction |
| malformed body/next link | malformed output | no unsafe traversal or cursor advance |
| partial page under budget exhaustion | explicit bounded truncation | never report unqualified success |
| duplicate/edit/delete observation | deterministic replay/update outcome | preserve idempotency and revision rules |

No provider exception, raw body, access token, or request URL crosses the
public adapter boundary.

## No-hidden-retry rule

The adapter performs one bounded attempt. SDK, HTTP client, proxy, middleware,
and orchestration layers must not add retries. Explicit user retry creates a
new approved operation and idempotency key.

## Official references

- [List channel messages](https://learn.microsoft.com/en-us/graph/api/channel-list-messages?view=graph-rest-1.0)
- [Metered APIs and services](https://learn.microsoft.com/en-us/graph/metered-api-list)
