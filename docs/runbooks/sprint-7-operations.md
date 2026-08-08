# Sprint 7 operator and user notes

## Supported capability truth

The web slice exposes released M2–M4 behavior plus redacted Sprint 7 settings.
Candidate confirmation is enabled only for `Requirement`; other assertion types
remain unavailable until a governed backend capability is released.

Settings reads return provider metadata, revision, health, and a boolean
credential status. They never return the credential, secret reference, graph
identifier, storage URL, or provider response body.

## Safe checks

Use `/health/live` for process liveness and `/health/ready` for the API/Semantic
Core dependency check. Request IDs are safe to share with an operator when
reporting an RFC 7807 problem. Do not paste provider keys, full request payloads,
or operational database files into tickets.

Run the configured source checks with:

```text
pwsh ./scripts/run_sprint7_validation.ps1
```

Use `scripts/run_sprint7_acceptance.ps1` only against a disposable Compose
project. It cleans its own volumes and restarts API/web before teardown.
