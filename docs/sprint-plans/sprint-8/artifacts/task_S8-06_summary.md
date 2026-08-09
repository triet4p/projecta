# Task Summary: Authorized project context and selection

**Sprint:** Sprint 8
**Task:** S8-06

## Summary of Work

Designed a server-owned project-context boundary with a finite typed catalog,
opaque navigation handles, active selection lifecycle, revision/stale handling,
request scoping, local experience limits, session state ownership, privacy
behavior, and cross-project regression requirements. The design explicitly
does not claim authentication, RBAC/ABAC, tenant administration, or production
authorization.

## Files Modified

* [project-context-selection.md](../../../architecture/project-context-selection.md) - Catalog, selection, scope, and local-profile contract.
* [sprint-8.md](../sprint-8.md) - Marked S8-06 complete.

## Testing

* **Test File:** N/A; this is an architecture/security contract artifact.
* **Status:** Passed.
* **Execution Command:** `git diff --check`; cross-checked the Sprint 7 context threat model, Application API boundary, Compose defaults, and project isolation rules.

## Additional Notes

The browser may carry an opaque navigation hint but never an authority-bearing
selection. Any implementation must preserve explicit stale/error behavior and
must not reintroduce `local-project` fallback.
