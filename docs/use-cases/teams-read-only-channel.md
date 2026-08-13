# Read-only Teams Channel Import — Sprint 11 S11-02

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-02

## Goal

Allow an authenticated Projecta user with server-owned project membership and
the `connector-admin` capability to bind one allowlisted Microsoft Teams
channel to one Projecta project and run one bounded, read-only import.

The import produces source/evidence artifacts and reviewable candidates using
the existing connector and semantic lifecycle. It never creates an asserted
fact directly and never performs an external side effect.

## Actors and authority

| Actor | Authority | Not allowed |
| --- | --- | --- |
| Project user | View only projects granted by server membership | Choose a project by raw ID or override principal headers |
| Reviewer | Read imported evidence and review candidates | Create/change an installation or access another project |
| Connector administrator | Create/update/enable/disable one Teams installation and run a bounded import | Read plaintext credentials, bypass project policy, send Teams data back |
| Projecta API | Own session, membership, secret reference, bounds, cursor, and lifecycle | Treat browser claims or provider display names as authority |
| Teams administrator | Provide app registration, consent, and disposable test channel | Put credentials or production payloads into repository artifacts |

## Installation scope

One installation binds:

- one Projecta project;
- one approved Microsoft 365 tenant;
- one Teams team and one channel;
- one opaque server-side secret reference;
- the reviewed inbound read-only capability;
- finite page, message, reply, byte, and deadline limits;
- a revision and idempotency policy owned by PostgreSQL.

Public DTOs expose only opaque installation/run handles, bounded status,
capability labels, safe setup guidance, and terminal outcomes. Provider IDs,
secret references, raw URLs, tokens, and raw payloads remain internal.

## Import bounds

The initial implementation must enforce all of these limits before adapter
execution and at every pagination step:

- one configured Graph host and allowlisted message paths;
- one absolute operation deadline;
- maximum root-message pages;
- maximum root messages;
- maximum replies per root and total replies;
- maximum event bytes and total evidence bytes;
- maximum next-link length and redirect count of zero;
- cancellation before each external request and before commit;
- no automatic retry, cursor movement, or partial semantic commit after a
  malformed or incomplete terminal result.

The exact numeric values are implementation parameters to be selected from
the G1-approved resource budget and the existing connector limits. They must
not silently exceed the released `connector-contract.v1` bounds.

## Acceptance journeys

1. **Sign-in and scope:** a user signs in through the reviewed OIDC boundary,
   sees only authorized projects, and loses access after logout, expiry,
   revocation, or membership removal.
2. **Least-privilege installation:** a connector administrator creates one
   allowlisted installation; a reviewer receives a safe forbidden result.
3. **Bounded import:** one explicit run retrieves finite root messages and
   replies, writes immutable evidence, and emits candidates through the
   existing lifecycle.
4. **Review continuity:** a reviewer can inspect candidate/evidence continuity
   through existing Review and Knowledge surfaces without provider-shaped
   public fields.
5. **Replay/restart:** the same import or a process restart does not duplicate
   evidence, source, candidate, run outcome, or committed cursor.
6. **Isolation:** users, projects, tenants, installations, evidence, runs,
   secret references, and semantic graphs cannot observe one another.
7. **Failure truthfulness:** invalid consent, `401`, `403`, `429`, timeout,
   malformed payload, invalid pagination, cancellation, and partial pages
   become finite terminal outcomes.
8. **Revocation and teardown:** provider permission is revoked, installation is
   disabled or removed, and sanitized evidence proves that no credential or
   raw tenant payload entered artifacts.

## Counterexamples

The use case is not satisfied if any of these occur:

- a browser-selected project or actor header changes authorization;
- a display name automatically merges a Teams identity into a Projecta Person;
- an adapter follows an arbitrary `@odata.nextLink`, redirect, or URL host;
- a Graph `429` causes hidden retries or advances a cursor;
- a partial page is reported as success without explicit truncation;
- raw Teams JSON, HTML, provider IDs, access tokens, or secret references
  appear in a public DTO, log, telemetry record, RDF graph, or artifact;
- imported content is written directly to asserted RDF without review;
- the live tenant or credential is required by public CI.

## Non-goals

- outbound messages, replies, task creation, uploads, or reactions;
- webhook ingress, continuous synchronization, background scheduling, or
  automatic retry;
- general tenant administration, generic ABAC, or a second real connector;
- automatic external-identity merge or Teams-specific ontology vocabulary.

## External prerequisites

Live acceptance requires a human-controlled Microsoft 365/Teams sandbox,
application registration, approved permissions/consent, and a disposable test
channel. Missing those inputs blocks S11-67 only; deterministic replay and
contract work must remain runnable without them.
