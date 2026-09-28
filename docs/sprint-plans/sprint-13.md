# Sprint 13 Plan — Evidence-first Assisted Authoring

Status: `SPRINT_REVIEW_PENDING_AFTER_DOCKER_ACCEPTANCE`

Contract: [Evidence-first Assisted Authoring v1](sprint-13/evidence-first-assisted-authoring.v1.md)

Sprint 12 is historical/closed for the dense-hard track. Its v1--v4
diagnostics and v5 easy baseline remain frozen evidence; this sprint changes
the active product direction to human-authored structured capture with bounded,
optional local AI suggestions.

## Sprint Goal

Deliver a safe, useful human-first authoring slice that captures evidence-bound
entities with zero model calls and adds AI only as an on-demand bounded copilot,
without reopening Sprint 12 evaluation or provider work.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done / [-] explicitly deferred

- [x] **S13-01 — Align direction and closure records:** Publish the evidence-first
  contract, mark Sprint 12 historical/closed, and remove active-plan language
  that treats whole-document extraction as the next product path. See
  [S13-01 summary](sprint-13/artifacts/task_S13-01_direction-alignment_summary.md).
- [x] **S13-02 — Implement zero-model entity capture:** Build the first vertical
  slice from human task/question or structured note through scoped evidence,
  server-owned SourceVersion/TextAnchor/opaque identity, append-only receipt,
  and approved-only materialization. Manual mode must work without a model call.
- [x] **S13-03 — Add on-demand local suggestion:** Add one bounded item/type/link
  suggestion after human occurrence/entity confirmation; enforce the server/model
  boundary, cache/dedup, budget checks and explicit decision states.
- [x] **S13-04 — Add controlled relations:** Permit relation suggestions only for
  same-project confirmed endpoints with deterministic evidence and allowlisted
  predicate/direction; cover rejection and stale-revision behavior.
- [x] **S13-05 — Add cost and correction telemetry:** Record per-workflow and
  per-accepted-assertion cost, correction burden and zero-model usage without
  raw source/prompt/provider payloads; keep RM-65 boundaries intact.
- [x] **S13-06 — Add adversarial and mutation tests:** Cover occurrence
  duplication, stale/cross-project anchors, endpoint swaps, unsupported
  predicates, quarantine over/under-count and unreviewed finalization; preserve
  RM-55--RM-66 regression evidence.
- [x] **S13-07 — Review vertical-slice gates:** Verify manual utility, safety,
  budget and receipt invariants. This is an implementation review only; it does
  not authorize R6/R7 or any provider, human, held-out or production study.
- [-] **S13-08 — Separately authorize offline evaluation (deferred):** After
  S13-02--S13-07 passed, the owner explicitly kept offline evaluation deferred.
  No offline protocol, R6 fresh benchmark, or R7 independent evaluation is
  authorized within this sprint.

The reopened runtime gate passed after an isolated full Docker Compose build
and a real browser-to-live-backend manual capture, review and controlled
relation flow. The earlier API/Java and controlled-browser evidence remains
separate; the Docker session verified receipt persistence and blocked graph
materialization, not optional live local-model inference or production release.
The documented Compose startup, web response contract, and optional-model
environment forwarding passed their task gates. The live Docker API preserved
distinct unconfigured and unavailable local-model errors: the no-model request
spent no budget, and the configured request without Ollama recorded one failed
attempt without an assertion or graph write. Successful local-model inference
was not exercised; a model was not provisioned in the API network namespace.
The receipt, relation, and final Docker API error-envelope corrections passed
fresh task-level evidence gates. Production API requests preserve actionable
relation and receipt reason codes without graph writes, and the API regression
suite remains green. Sprint-wide differential re-review is pending. S13-08
remains deferred; the owner-waived project graph refresh remains stale.

## Notes / Blockers

- No provider call, external custody, human study, held-out inspection,
  production enablement, ontology release, selection, promotion or release is
  authorized by this plan.
- The dense-hard remediation backlog remains historical diagnostic input. Its
  R1--R5 concerns are mapped into this human-first workflow; R6/R7 are closed.
- Any ontology term or SHACL change requires `$projecta-evolve-ontology` and
  human semantic approval.
