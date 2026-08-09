# Task Summary: Correlated logging contract

**Sprint:** Sprint 8
**Task:** S8-04

## Summary of Work

Defined one allowlisted structured event schema for browser boundary, Nginx,
Application API, Semantic Core, Fuseki gateway, provider attempts, audit, and
Compose health. The contract specifies request/operation correlation,
project-safe scope, attempt and terminal outcome semantics, event vocabulary,
propagation rules, conditional fields, redaction denylist, operational
guarantees, and cross-container regression requirements.

## Files Modified

* [correlated-logging.md](../../../architecture/correlated-logging.md) - Shared event schema and propagation contract.
* [sprint-8.md](../sprint-8.md) - Marked S8-04 complete.

## Testing

* **Test File:** N/A; this is a logging contract artifact.
* **Status:** Passed.
* **Execution Command:** `git diff --check`; cross-checked current extraction telemetry, configuration audit, Nginx forwarding, and Semantic Core request/problem fields.

## Additional Notes

The contract keeps correlation separate from authorization and treats existing
partial telemetry as implementation evidence, not as an already-complete S8
schema. It remains proposal-only pending G1.
