# Sprint 11 Amended G2 Review Packet

Status: `G2_APPROVED_RELEASE_PREPARATION_PENDING`

G2 product/security/release approval: `APPROVED_WITH_RESIDUAL_RISK` on 2026-08-14
Ontology semantic reuse approval: `APPROVED_BY_PROJECT_OWNER` on 2026-08-13

This packet records the project owner's G2 approval and the accepted anonymous
GitHub quota residual risk. It does not publish `v0.6.0` or grant G3
exact-commit approval.

## Decision record

The project owner approved the amended release boundary: GitHub Public Issues
is the one live,
credential-free, read-only connector for exactly one disposable public
repository. Teams remains experimental/deferred and S11-67 is not a release
blocker. Baseline live acceptance r9 is accepted as the external-provider
proof. A second quota-consuming live edit/replay run is waived; deterministic
edit/replay, cursor, provenance, tamper, and isolation contracts are the
substitute evidence for this release.

## Architecture and threat boundary

The implementation reuses `ConnectorPolicy`,
`ConnectorSyncOrchestrator`, the finite registry/composition root, canonical
event validation, evidence store, and PostgreSQL repository. The GitHub
adapter uses fixed `https://api.github.com`, no provider token, no redirects,
no hidden retry, bounded pagination, cumulative 10 MiB/run response budget,
100 events/run, 1 MiB/event, and a 30-second deadline. Only issues and issue
comments are mapped; pull requests and their comments are excluded.

OpenBao remains the platform secret boundary. The connector has no provider
secret, but this does not remove the platform boundary. No work tenant,
customer data, paid managed service, or production payload is part of this
release slice.

## API/UI maturity matrix

| Surface | GitHub Public Issues | Teams |
| --- | --- | --- |
| Catalog/API maturity | Live, credential-free, read-only | Experimental/deferred |
| Setup | Server-owned single-use handle bound to actor/project/installation/revision | Operator tenant/team/channel setup |
| Runtime proof | Deterministic suites plus one disposable public live journey | Deterministic replay regression only |
| Release impact | Required for `v0.6.0` | S11-67 explicitly non-blocking |

## Validation totals

Recorded on 2026-08-13 from the review rerun:

| Suite | Result |
| --- | --- |
| Full API pytest | `247 passed, 5 skipped` |
| Targeted GitHub/API tests | `50 passed` |
| Sprint 11 contract selection | `36 passed` |
| Web tests | `17 passed` |
| Ruff | `pass` |
| Strict Pyright | `0 errors, 0 warnings` |
| TypeScript typecheck and API drift | `pass` |
| Baseline live evidence validator | `pass` for r9 baseline artifact |
| Edit/replay evidence contracts | `pass`; live journey rerun waived by G2 |
| `git diff --check` | `pass` |

CI remains provider-independent; the live journey is a separate human review
gate and is never required for ordinary deterministic CI.

## Evidence inventory

The hashes below bind the exact artifacts reviewed at G2. The failed journey is
retained as a diagnostic record rather than represented as passing evidence.

| Artifact | Purpose | SHA-256 |
| --- | --- | --- |
| `artifacts/s11-A18-github-live-acceptance.json` | Passing r9 baseline import, PR exclusion, exact delta, replay, isolation | `ca4883f8158be882717074dce2d398a58d53ccb58b2004e1f0adb74608a0f9d1` |
| `artifacts/s11-A18-github-live-journey.json` | Failed quota-limited edit/replay diagnostic retained under the G2 waiver | `24066b08617b5d786cf1f3947f9cc543214aba69f36e98ef96c40480a72d378c` |
| `artifacts/s11-66-clean-compose.json` | Clean production-shaped Compose gate | `bffc14e403644a3285fb3eec69f15c0854c9ff5fe01a1cca31fc813ec9fe126d` |
| `artifacts/s11-63-cold-recovery.json` | Coordinated recovery and post-restore replay | `7141ec7d2caf901bfde6ae9d0f74ff21a9db8456affa4b38e8e463d2305d582b` |
| `artifacts/s11-65-validation-remediation.json` | Validation remediation gates | `b05a14f98920e07d42a9b184f3ae73d5c279afc8012cad24615ff48a6c587504` |

## Clean Compose and recovery provenance

- Clean Compose artifact: `passed`, schema `sprint11.clean-compose.v2`,
  2026-08-13 03:14:20Z–03:17:28Z; interpolation, stateful foundations,
  OpenBao initialization/unseal, production topology, readiness, and release
  checks are recorded with sensitive output redacted.
- Cold recovery artifact: `passed`, schema `sprint11.cold-recovery.v2`,
  2026-08-13 03:33:03Z–03:35:21Z; source destruction, restore, manual unseal,
  session invalidation, workload re-authentication, and idempotent replay are
  recorded.

## Resource observations

The following is a point-in-time local Compose observation captured at
2026-08-13T14:23:59Z on an 8 GiB Docker host. It is an observation, not a
capacity or production-load guarantee.

| Container | CPU | Memory | PIDs |
| --- | ---: | ---: | ---: |
| API | 0.26% | 100.9 MiB / 7.761 GiB | 2 |
| Semantic Core | 0.25% | 151.8 MiB / 7.761 GiB | 34 |
| PostgreSQL | 0.01% | 39.43 MiB / 7.761 GiB | 7 |
| Fuseki | 0.22% | 468.9 MiB / 7.761 GiB | 28 |

No subscription, Azure billing, work tenant, or provider credential is needed.

## Live evidence disposition

The executable producers generate the artifacts; hand-editing an artifact is
not evidence. The validator binds run state/count/cursors and normalized
timestamps through a provenance digest, binds snapshot cardinality to a
sanitized record digest, and requires exact pre/post candidate deltas.

`baseline finished → before-edit snapshot → before-edit run → after-edit snapshot → after-edit run → replay → cleanup`

The accepted r9 baseline imports exactly 2 issues plus 2 issue comments, excludes at
least 1 pull request (and any PR comments), create exact project-scoped
candidate/evidence delta, and return `replayed` for the same idempotency key.
The checked-in deterministic contracts require edit observations to produce
different sanitized record digests and require replay to match the after-edit
run digest, event count, and committed cursor. The attempted r9 edit journey
failed safely after anonymous quota exhaustion and remains a diagnostic
artifact. G2 explicitly waives another live attempt to avoid consuming free
provider quota; empty or truncated baseline runs remain unacceptable.

## Unresolved risks and non-goals

- Unauthenticated GitHub API capacity and availability remain external limits;
  deterministic rate-limit/failure mapping does not remove that risk.
- Live edit/replay was not completed after the final provenance remediation.
  G2 accepts deterministic coverage as substitute evidence and makes no claim
  about GitHub capacity, availability, or continuous synchronization.
- Scope is public read-only ingestion, not private/authenticated GitHub,
  webhooks, outbound actions, HA, or generic tenant administration.
- Teams live acceptance is deferred and requires a separately authorized
  tenant, consent, secret custody, cleanup, and live-evidence decision.
- v0.6.0 version/changelog freeze, immutable preflight, G3 exact-commit
  approval, and publication remain open.

## Reviewer checklist and decision rule

- [x] Baseline and diagnostic edit artifacts were generated by checked-in producers.
- [x] Artifact SHA-256 inventory matches the files reviewed.
- [x] Baseline validator passes; deterministic tamper contracts reject changed
      run digests, cursors, timestamps, and edit snapshot digests.
- [x] Baseline exact event counts, PR exclusion, downstream delta, replay, and
      project isolation are present; live edit/replay is explicitly waived.
- [x] Clean Compose and cold recovery artifacts are `passed` and their
      timestamps/digests are recorded.
- [x] Test totals, resource observations, residual risks, and Teams deferral
      are accepted as stated.
- [x] Reviewer confirms no work tenant, provider token, customer data, or
      paid managed service is required.

The project owner accepts the recorded residual risk and approves G2. This
waiver is narrow: it does not convert the failed diagnostic journey into
passing evidence and does not expand the connector claim beyond bounded,
credential-free public read-only ingestion.

## Approval record

- Ontology semantic reuse approval: `APPROVED` by project owner on 2026-08-13
- G2 product/security/release approval: `APPROVED_WITH_RESIDUAL_RISK` by project owner on 2026-08-14
- Immutable `v0.6.0` preflight: `PASSED` on exact commit
  `686a2b9b141d01c81b465de8a5cad8c15452c268`; clean Compose, cold recovery,
  S11 validation, and Sprint 10 validation passed. External evidence digests:
  clean Compose `56798c27ac507cb33f9f7ce7a962eb4d8d9ef8a17c48022e6f14157468587ef7`,
  cold recovery `0cd9f8e7df22a240f2135a73216cda6aae92e655dc264fea4fc26ffc46acd974`,
  S11 validation `d2a26b1cd6861495d1344a657892b10387ac7dbc54a1469a831ad86d92d85953`,
  Sprint 10 validation `f244fadf7bb4da071778fe5ac7f39a4409d584593e43c526df96b2ab819796ba`.
- G3 exact commit approval: `APPROVED_BY_RELEASE_AGENT` for exact commit
  `686a2b9b141d01c81b465de8a5cad8c15452c268`; annotated tag publication remains
  gated on release CI terminal success.
- Publication: `PENDING`
