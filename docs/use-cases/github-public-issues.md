# GitHub Public Issues Read-only Use Case — Sprint 11 S11-A02

**Status:** `CONTRACT_FROZEN_FOR_S11_IMPLEMENTATION`

**Task:** S11-A02

## Outcome

An authenticated Projecta user with project membership and `connector-admin`
capability installs exactly one public GitHub repository for one Projecta
project. A bounded manual run reads only repository issues and issue comments,
then maps them into the existing source, evidence, candidate, provenance, and
review lifecycle.

The connector is credential-free and never uses a work tenant, GitHub token,
GitHub App, OAuth grant, private repository, or provider write operation.

## Actors and trust boundaries

| Actor | Responsibility | Trust boundary |
| --- | --- | --- |
| Projecta connector administrator | Chooses the owner/repository pair and starts a bounded run | Public API validates capability; browser is not an authority |
| Projecta reviewer | Reads safe run/source/candidate projections | Cannot install, mutate, or access another project |
| Projecta server | Owns installation scope, provider origin, limits, cursor, evidence commit, and semantic orchestration | Authoritative operational and policy boundary |
| GitHub REST API | Supplies public issue/comment observations | Untrusted external evidence source |
| GitHub actor | Appears only as a bounded non-authoritative actor hint | Never auto-merged into a Projecta `Person` |

## Installation scope

The installation binds one validated pair:

```text
connectorType: github-public-issues
owner: one GitHub owner
repository: one GitHub repository
apiOrigin: https://api.github.com (server constant)
```

The browser submits only bounded `owner` and `repository` fields through an
authorized setup operation. The server probes visibility, issues a short-lived
single-use opaque setup handle, and consumes it into the server-owned
installation snapshot. A public display label is separate from the internal
authorization identity.

## In-scope provider data

- Repository issues from `GET /repos/{owner}/{repository}/issues`.
- Repository issue comments from `GET /repos/{owner}/{repository}/issues/comments`.
- Issue and comment edits represented as new immutable source observations.
- Open/closed state changes represented as issue updates.
- Provider timestamps, numeric IDs, title/body/state, safe label names, and
  bounded actor hints needed for deterministic evidence and replay.

Pull requests, review comments, discussions, projects, notifications,
commits, attachments, HTML pages, arbitrary linked resources, and provider
identity merges are out of scope. An issue-shaped response containing a
`pull_request` member is excluded.

## Bounds and first-run policy

Each run keeps the existing connector limits:

- at most 100 canonical events;
- at most 10 MiB of evidence across the run;
- at most 1 MiB of evidence per event;
- one absolute 30-second deadline;
- one bounded provider attempt with no SDK, HTTP-client, proxy, or middleware
  retry;
- at most 20 provider requests per run, with no more than 10 pages per stream;
- `per_page=100` on the two initial streams.

The first run uses a server-owned 30-calendar-day lookback from the run start.
The browser cannot widen or replace this lookback. If the provider traversal
reaches any bound, the run is explicitly `truncated`; it does not advance the
cursor as though the full repository history had been imported.

## Primary journeys

### UJ-01 — Install and import

1. A connector administrator selects a project and submits a valid public
   owner/repository pair.
2. Projecta validates the pair, probes only the fixed GitHub origin, and
   creates the installation from a single-use setup handle.
3. The administrator starts one bounded read-only run.
4. The server fetches issues and comments, excludes pull requests, stores
   bounded evidence, validates canonical events, and reuses the existing
   source/candidate/provenance lifecycle.
5. The reviewer sees safe counts, run outcome, evidence, and pending candidates
   scoped to the selected project.

### UJ-02 — Edit and replay

1. An issue or comment is edited at GitHub.
2. A later run uses inclusive watermarks and emits a distinct immutable
   revision for the changed provider timestamp.
3. Repeating the same run/revision returns the existing idempotent outcome and
   creates no duplicate source, evidence, candidate, or provenance mutation.
4. A failed or truncated run leaves the committed cursor unchanged.

### UJ-03 — Isolation and safe failure

1. A reviewer from another project cannot observe installation existence,
   setup handles, provider identifiers, evidence, or candidates.
2. Invalid repository pairs, private/nonexistent repositories, malformed
   provider output, unsafe pagination, rate exhaustion, and timeout produce
   finite safe outcomes without raw provider payloads or cursor movement.
3. The same provider pair installed in another project remains operationally
   distinct and cannot collide on event identity.

## Counterexamples

- A full `https://github.com/...` or `https://api.github.com/...` URL is not a
  repository configuration.
- A `Link` header pointing to another host, scheme, repository, endpoint, or
  query shape is never followed.
- A pull request is not imported as an issue, even though GitHub exposes it
  through the issues endpoint.
- A provider login is not a Projecta principal and never creates a `Person`
  assertion by name alone.
- A partial page is not reported as complete success.
- A provider URL, raw response envelope, token, IP address, ETag, or complete
  actor object is not persisted in a public projection.

## Explicit non-goals

No provider writes, webhooks, continuous polling, background scheduling,
private data, GitHub credentials, organization discovery, arbitrary repository
search, hidden retry, direct asserted RDF, or work-tenant acceptance is part of
this use case.

## Acceptance definition

The use case is satisfied when deterministic fixtures and the later disposable
public-repository journey prove install, bounded import, edit, replay,
pull-request exclusion, safe truncation/failure, evidence/candidate
continuity, and project isolation without retaining production or personal
data.

## Official references checked 2026-08-13

- [GitHub REST issues](https://docs.github.com/en/rest/issues/issues)
- [GitHub REST issue comments](https://docs.github.com/en/rest/issues/comments)
- [GitHub REST API versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions)
- [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
