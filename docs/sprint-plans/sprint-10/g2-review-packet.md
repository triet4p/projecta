# Sprint 10 G2 product, security, and semantic readiness packet

## Status

`HUMAN_APPROVED` (2026-08-11)

**Scope:** S10-11 through S10-67 implementation and validation artifacts.

**Approval gate:** S10-68 was approved by explicit human confirmation in the
Codex task on 2026-08-11. This approval authorizes version alignment, changelog
freeze, release-contract verification, and immutable release preflight. It does
not authorize G3, tag creation, publication, or production authentication
changes.

## Approval record

- Decision: `Approve G2 Sprint 10`
- Scope: Sprint 10 product, security, and semantic readiness through S10-68
- Approval source: explicit user confirmation in the Codex task
- Date: 2026-08-11
- Release boundary: G3 must still explicitly name and authorize the exact
  immutable release commit before push or tag publication.

## Review summary

Sprint 10 adds a deterministic inbound JSON/Mock connector behind server-owned
authorization, bounded canonical events, PostgreSQL operational state,
immutable evidence, and the existing Note/NoteItem candidate/provenance
lifecycle. The public API and Connections UI expose opaque handles and safe
status only. Connector operational state remains outside RDF.

The implementation passed G2 review. S10-67 passed on clean ephemeral
validation commit `c2789f915ab72f98779c0d710a7d14280510bf2d`, followed without
source changes by clean-volume acceptance and isolated recovery. This commit is
validation evidence only; it is not a release commit and does not authorize a
tag.

## Architecture and semantic reuse

| Boundary | Evidence | Review outcome |
| --- | --- | --- |
| Adapter/event | [connector contract](F:/ai-ml/projecta/docs/architecture/connector-contract.md), [canonical event](F:/ai-ml/projecta/docs/architecture/canonical-event-contract.md) | JSON/Mock only; bounded, inbound, single-attempt, replay-safe |
| Authorization | [authorization contract](F:/ai-ml/projecta/docs/architecture/connector-authorization.md) | Server-owned principal and project policy; no browser authority |
| Persistence | [operational storage](F:/ai-ml/projecta/docs/architecture/connector-operational-storage.md) | PostgreSQL owns installations, inbox, runs, cursors, audit, dead letters |
| Evidence | [evidence storage](F:/ai-ml/projecta/docs/architecture/connector-evidence-storage.md) | Immutable, content-addressed, bounded, project-scoped evidence |
| Semantic Core | [semantic source adapter](F:/ai-ml/projecta/apps/api/src/projecta_api/connectors/semantic_source.py) | Reuses released capture boundary; connector cannot assert directly |
| Ontology | [reuse-gap audit](F:/ai-ml/projecta/docs/ontology/sprint-10-connector-reuse-gap.md) | `NO_ONTOLOGY_CHANGE_REQUIRED`; no new vocabulary introduced |

## API/UI matrix

| Surface | Covered behavior | Evidence |
| --- | --- | --- |
| API | Catalog, project-scoped installation CRUD/toggle, run/list/read/retry, safe problems, opaque handles | `apps/api/tests/test_connector_public_api.py`, generated API snapshot |
| UI | Install, enable, run, status, live announcement, narrow layout, secret/internal-ID absence | `apps/web/tests/e2e/sprint10.spec.ts`, `apps/web/tests/e2e/sprint10.real.spec.ts` |
| Isolation | Project predicates, forbidden/not-found mapping, no raw secret/storage/RDF fields | `scripts/check_sprint10_repository_contract.py`, authorization tests |

## Validation evidence recorded so far

- S10-61 clean-checkout matrix: `status=passed`, all 24 gates at native exit 0,
  API `170 passed, 5 skipped`, web unit `17 passed`, deterministic browser
  `6 passed`, Semantic Core `50 passed, 7 skipped`, ontology `140/140`, and
  connector migration/integration `2 passed`. The JSON records
  `worktreeWasClean=true` and `allowDirtyWorktree=false`.
- S10-62 isolated acceptance: real-browser `2 passed`; Journeys 2–6 passed
  with `11`, `1`, `9`, `3`, and `2` tests respectively; post-restart real
  browser `1 passed`; safe-log checks passed; clean volumes were removed.
- S10-63 isolated recovery: `status=passed`, all 8 steps exit 0, restored
  evidence verified, and replay outcome was `replayed`.
- Contract suite: `31/31` release-contract tests passed; Semantic Core Maven
  verification passed with 50 tests and 7 baseline skips.

## S10-67 evidence

- [Clean validation JSON](artifacts/s10-61-validation.json) records the complete
  matrix and native exit codes.
- Clean-volume production-shaped Compose acceptance passed all seven journeys,
  restart persistence, correlated safe-log scanning, and cleanup.
- The release-workflow contract suite passed `31/31` on the clean snapshot.
- Baseline skips are unchanged: five API integration/environment skips and
  seven Semantic Core baseline skips. No Sprint 10 required gate is skipped.

## Residual risks and unresolved choices

- Production authentication, RBAC/ABAC administration, and managed secret
  storage remain outside Sprint 10 and must not be inferred from local
  experience mode.
- No real external connector or outbound side effect is implemented.
- The exact release commit will differ after G2-authorized version/changelog
  alignment; S10-72 therefore requires the entire immutable preflight again.
- Production identity and managed secret storage remain explicit Sprint 11+
  boundaries; local experience authorization must not be presented as either.

## Human review outcome

The human reviewer approved the implementation boundaries, seven acceptance
journeys, authorization/isolation behavior, semantic reuse outcome, recovery
evidence, residual risks, and S10-67 evidence. Version and changelog alignment
plus immutable preflight may proceed. Tagging and publication remain blocked on
G3 approval of the exact release commit.
