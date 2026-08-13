# Task Summary: S11-A14 — Make Provider Maturity Truthful

## Outcome

GitHub Public Issues is presented as the credential-free live connector for
`v0.6.0` across the catalog projection, Connections UI, user runbook, G1
approval record, and changelog. Microsoft Teams remains available for
deterministic regression coverage but is explicitly experimental/deferred and
does not block the amended release target.

The canonical event validator and source-mapping boundary now accept GitHub
events and reuse the existing connector capture path. Failure telemetry no
longer hardcodes `json-mock` when a different connector reaches terminal
failure.

## Status

`DONE`
