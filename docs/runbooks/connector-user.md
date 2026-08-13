# Connector user runbook

## GitHub Public Issues setup

Open **Connections** inside a selected project. GitHub Public Issues is the
`v0.6.0` live connector. Paste only the short-lived, operator-issued
`setup_…` handle that binds one exact public repository, then install and
enable it. No token, tenant, or arbitrary provider URL is accepted by the
browser or public API.

The connector reads only public issues and issue comments from the fixed
GitHub API host. Pull requests are excluded. Imported material becomes a
reviewable candidate; it is not an assertion until a human reviews it through
Review Queue.

## Local JSON/Mock setup

Open **Connections** inside a selected project. Choose the server-approved
`fixture://` reference, install the JSON/Mock connector, and enable it only
after checking the selected project. JSON/Mock remains available for local
deterministic replay. Microsoft Teams is retained for regression coverage but
is experimental/deferred for `v0.6.0` and is not the live release connector.

The fixture content is bounded to the published connector limits: at most 100
events per run, 1 MiB per event/evidence object, 10 MiB per pull, and a 30-second
run deadline. An imported source becomes a reviewable candidate; it is not an
assertion until a human reviews it through Review Queue.

## Status and retry

`Running`, `Succeeded`, `No new events`, `Replayed`, `Failed`, `Cancelled`, and
`Unavailable` are server-reported states. A failed run may show a dead-letter
record. Retry is explicit, bounded to one visible retry, and can be rejected as
stale when another operation changed the installation or run revision.

Never paste credentials, raw provider payloads, internal IDs, RDF graph names,
storage paths, GitHub repository URLs, or setup handles into a fixture reference
or support ticket.

## Safe escalation

Include the visible request ID, project handle, connector type, state, and
revision. Do not include credentials, raw imported content, event IDs, evidence
references, or screenshots containing secret fields. If a project is forbidden
or not found, reselect the project; do not retry by changing headers.
