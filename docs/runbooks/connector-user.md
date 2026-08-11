# Connector user runbook

## Local JSON/Mock setup

Open **Connections** inside a selected project. Choose the server-approved
`fixture://` reference, install the JSON/Mock connector, and enable it only
after checking the selected project. This Sprint 10 slice has one connector;
real provider connectors are intentionally unavailable.

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
or storage paths into a fixture reference or support ticket.

## Safe escalation

Include the visible request ID, project handle, connector type, state, and
revision. Do not include credentials, raw imported content, event IDs, evidence
references, or screenshots containing secret fields. If a project is forbidden
or not found, reselect the project; do not retry by changing headers.
