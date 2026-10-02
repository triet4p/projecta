# Projecta Global Plan

## Overview

Xây Projecta theo các vertical slice có thể kiểm chứng, bắt đầu từ Quick Note thủ công và semantic lifecycle. Ontology đi trước từng slice như domain contract, nhưng mỗi increment phải đi kèm dữ liệu mẫu, competency query và automated validation; không thiết kế toàn bộ ontology trước khi có use case.

## Planning Principles

- Mỗi term/rule mới phải phục vụ competency question hoặc governance requirement.
- Mỗi semantic change đi qua `$projecta-evolve-ontology` và human approval.
- Ưu tiên đường chạy end-to-end nhỏ hơn infrastructure breadth.
- Manual/Mock connector đi trước provider thật; GitHub Public Issues
  credential-free đi trước connector cần tenant/consent; deterministic fixture
  đi trước live-provider acceptance.
- Không thêm Kafka, OpenSearch, Kubernetes hoặc full observability trước khi volume/SLO yêu cầu.
- Chất lượng business và semantic phải được chứng minh trên dataset có governance,
  held-out evaluation và human review trước khi tiếp tục mở rộng capability.

## Milestones

- [x] **M1 — Executable Semantic Foundation (Sprints 1–3):** Ontology kernel, SHACL/provenance lifecycle và Jena Semantic Core chạy thật.
- [x] **M2 — Manual Quick Note Slice (Sprint 4):** Typed note → deterministic
  candidate → human review → assertion/evidence qua API tối thiểu; giữ inference
  boundary nhưng chưa materialize rule chưa được duyệt.
- [x] **M3 — LLM Extraction and Evaluation (Sprint 5):** Released 2026-08-03;
  corrected live-quality gate passed twice consecutively after implementation,
  ontology and clean canonical Compose validation completed.
- [x] **M4 — Retrieval and Coordination (Sprint 6):** Project-scoped queries, requirement history, blockers và evidence-backed answers.
- [x] **M5 — Product Experience and Runtime Configuration (Sprint 7):**
  Containerized React web experience cho Quick Note, candidate review,
  evidence-backed retrieval và user-managed LLM configuration qua secret
  boundary được review và human-approved ngày 2026-08-09; evidence follow-up
  còn lại được ghi nhận trong review packet như risk không-gating.
- [x] **M6 — Truthful Multi-Project Graph Experience (Sprint 8):** Fail-explicit
  runtime diagnostics, polished light/dark data-workspace UI, project
  catalog/navigation, finite graph projection và structured Note Composer không
  yêu cầu người dùng nhập opaque ID.
- [~] **M7 — Connector and Production Evolution (Sprint 10+):** Mock/manual
  connector framework, connector thật đầu tiên, authentication/authorization,
  security và production hardening. Sprint 11 and `v0.6.0` are complete. M7
  remains open; Sprint 14 prioritizes the owner-recorded end-to-end experience,
  user-facing packaging, and portable data over additional connector breadth.
- [x] **M8 — Business Semantic Quality and Evaluation (Sprint 12):** Governed
  atomic and longitudinal datasets, leakage-resistant splits,
  ontology/graph/retrieval metrics, controlled optimization, sealed held-out
  evaluation, and target-role business acceptance. The historical synthetic
  corpus and rejected prompt experiments are retained as evidence. G3.1-A/B/C
  are complete with scope limits; M8 has completed the single bounded v9
  development Stage A execution, which is preserved as a hard-gate-rejected
  report. RM-47 closed the v9 run rejected with no Stage B; RM-52 prepared the
  offline closure packet and prioritized error backlog; RM-53 accepted offline
  custody only; RM-54 accepted the revised human-first design for RM-55
  contract definition only; RM-55 accepted the SourceVersion/source-receipt
  contract; RM-56 accepted the versioned TextAnchor coordinate contract and
  RM-57 accepted the per-item validation/quarantine boundary; RM-58 accepted
  the confirmed-entity relation gate; RM-59 accepted deterministic relation
  evidence selection; RM-60 accepted the constrained relation contract and
  RM-61 accepted durable append-only review decision receipts; RM-62 accepted
  the source-first review workbench contract; RM-63 accepted the disabled-by-
  default approved-only assertion materialization boundary; RM-64 accepted
  versioned inference invalidation/rebuild; RM-65 accepted correction-burden
  telemetry; RM-66 accepted the offline adversarial/default-path gate and
  RM-67 accepted the closed-world human correction-burden contract. The frozen
  v5 source-only candidate and primary-agent proxy review remain preserved as
  a bounded baseline, but dense-hard v1 is now authoritative diagnostic
  evidence and fails the edit-burden gate. Phase F-RF is therefore
  `F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED`:
  the v5 60 supported finalized-for-review assertions, zero unsupported
  assertions, 12/12 unchanged items, and zero provider calls remain historical
  baseline evidence only. Dense-hard v1/v2/v3/v3.1/v4 diagnostics remain
  separate; v4 fails both stratified gates and requires the finite strategy-
  redesign backlog. No generalized “good enough” or low-correction claim
  follows. RM-68 remains internal-only and blocked for external validation;
  remediation requires new authority and a fresh strategy/packet.
  No external human, business-quality, provider, held-out, production,
  selection, promotion, or release claim follows. Sprint 12 is historical and
  closed; Sprint 13 implementation review is closed, and Sprint 14 is planned.
- [ ] **M9 — End-to-end Experience and Portable Delivery (Sprint 14):** Link
  existing functionality into usable journeys, improve UI/UX, provide a
  Docker-free user-facing run path and a safe cross-installation data handoff.
  Direct user experience must pass before a separately approved `1.0.0`
  release; Sprint 14 planning is not release authorization.

## Completed Sprints

- [Sprint 1 — Ontology Kernel](sprint-plans/sprint-1.md) — *Completed
  2026-07-28; ontology v0.1 approved and validated.*
- [Sprint 2 — Governed Knowledge Lifecycle](sprint-plans/sprint-2.md) —
  *Completed 2026-07-29; ontology v0.2 approved with 73/73 checks passing.*
- [Sprint 3 — Executable Semantic Core](sprint-plans/sprint-3.md) — *Completed
  2026-07-30; Fuseki-backed runtime and M1 human-approved.*
- [Sprint 4 — Manual Quick Note Slice](sprint-plans/sprint-4.md) — *Completed
  2026-08-01; M2 and ontology v0.3.0 human-approved and released.*
- [Sprint 5 — LLM Extraction and Evaluation](sprint-plans/sprint-5.md) —
  *Completed 2026-08-03; M3 and ontology v0.4.0 released after deterministic
  gates and two consecutive corrected live-quality passes.*
- [Sprint 6 — Retrieval and Coordination](sprint-plans/sprint-6.md) — *Completed
  2026-08-04; governed v0.5 inference snapshots, content-addressed Fuseki-backed
  retrieval/inference, grounded API answers, evaluation, and clean Compose
  acceptance passed.*
- [Sprint 7 — Web Experience and User-Managed Runtime Configuration](sprint-plans/sprint-7.md)
  — *Completed 2026-08-09; M5 product/security acceptance approved, with
  remaining evidence follow-up tracked in the review packet.*
- [Sprint 8 — Truthful Multi-Project Graph and Structured Notes](sprint-plans/sprint-8.md)
  — *Completed 2026-08-10; M6 human-approved after fail-explicit, project
  isolation, bounded Graph, structured Note, full regression, clean Compose,
  and production UI acceptance evidence.*
- [Sprint 9 — Provider Runtime Truthfulness](sprint-plans/sprint-9.md) —
  *Completed 2026-08-10; provider calls are single-attempt and bounded,
  correlation is preserved, and existing structured Notes project into Graph
  and Review Queue without rewriting stored RDF.*
- [Sprint 10 — Governed Connector Foundation and v0.5.1 Recovery](sprint-plans/sprint-10.md)
  — *Completed 2026-08-11; the governed JSON/Mock connector foundation,
  PostgreSQL/evidence recovery, project isolation, clean-Compose acceptance,
  immutable release gates, and public `v0.5.1` recovery release passed. The
  failed `v0.5.0` tag remains unchanged as historical evidence.*
- [Sprint 11 — Free Production-Shaped Trust Boundary and GitHub Public Issues Ingestion](sprint-plans/sprint-11.md)
  — *Released and closed 2026-08-14 as public non-draft `v0.6.0` from exact
  commit `4a4fa99e010f22a69667119554580c91e2fc7b7e`; CI/publish run
  `31767397618` passed. Sanitized evidence was retained and disposable runtime
  resources were torn down. M7 remains open.*

- [Sprint 13 — Evidence-first Assisted Authoring](sprint-plans/sprint-13.md)
  — *Implementation review closed 2026-09-29 after passing task evidence and
  sprint-wide differential gates. Full Docker browser-to-live-backend capture,
  review, relation and persisted receipt flows passed; manual rejection,
  controlled-relation and optional local-model failure boundaries were verified
  through the live Docker API. No successful model inference was claimed.
  Offline evaluation/R6/R7 remain deferred, production materialization remains
  locked, and the owner-waived project graph remains stale.*

## Active Sprint

- [Sprint 14 — End-to-end Experience and Portable Delivery](sprint-plans/sprint-14.md)
  — *In progress; S14-01–08 passed task evidence review. The owner approved the
  Windows 11 x64 per-user native launcher boundary and a hybrid online installer
  with official prerequisite downloads and prerequisite UAC. S14-08 closed
  after unsigned-scope evidence PASS and verified source checkpoint
  `4716daaa4ff727e163604db5aaf3d93d51828210`.
  The latest R1 local
  unsigned package/archive and NSIS candidate include build-source provenance
  and have scoped integrity/runtime audits. A frozen developer-host smoke under
  isolated data reached all four services, captured an exact source span,
  recorded a manual review receipt, and verified stop/restart persistence and a
  safe port-collision failure. The owner now confirms successful installation
  and all four machine-2 QA checks, and explicitly selected unsigned S14-08
  task closure. Clean-Windows/resource-floor, real missing-runtime vendor
  execution, and signing remain separate open release gates, not passed proof.
  S14-12/S14-13 criteria are unchanged. No public binary is available.
  Exact candidate identities are recorded in the task
  handoff. [Owner requirements](sprint-plans/sprint-14-requirements.md) cover
  function sufficiency, UI/UX, end-to-end workflows, Docker-free user packaging
  and data transfer. A direct owner/target-user experience gate must pass before
  separate `1.0.0` release approval. S13-08 offline evaluation and production
  materialization remain closed pending separate authority.*

## Historical / Closed Sprint

- [Sprint 12 — Business Semantic Quality and Evaluation](sprint-plans/sprint-12.md)
  — *Development-complete with the v5 internal agent-proxy PoC retained as a
  historical baseline under
  `F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED`;
  dense-hard v4 fails both stratified gates and external validation remains closed.
  Dataset v3,
  measurement remediation and the two-step f12 development execution package
  are frozen. RM-23F issued the preregistration/freeze and RM-25 authorized one
  exact 144-call development Stage A execution after independent owner review;
  the immutable report is schema-valid but rejected by hard, threshold and
  slice gates. RM-27 closed f12 rejected with no Stage B; RM-29 approved the
  finite schema/evidence remediation for offline implementation and mock tests
  only. RM-31 prepared the superseding lineage and RM-33 issued its v8
  preregistration and technical freeze only. Provider authorization, output,
  validation, held-out access, Stage B, selection and promotion remain closed;
  RM-34 preparation and custody reconciliation are complete; RM-35 authorized
  exactly one new v8 execution. RM-36 invoked it once and failed before v8
  report persistence; the authorization is spent and no retry is permitted.
  RM-37 closed the failed execution and opened only offline reconciliation
  diagnosis/remediation preparation. RM-39 approved offline implementation;
  RM-40 implemented the versioned remediation path; RM-43 issued the corrected
  v9 preregistration and technical freeze. RM-44 prepared the exact v9
  authorization offline and RM-45 issued exactly one bounded v9 Stage A
  authorization. RM-46 executed exactly once and preserved the schema-valid but
  hard-gate-rejected v9 report; RM-47 closed the experiment rejected with no
  Stage B and opened only offline v6/v9 error-analysis preparation. The v6/v9
  comparison does not establish quality improvement. RM-48 has prepared the
  sanitized comparison/options packet; RM-49 approved sequential offline
  diagnostics then parity-fixture work, and RM-50 completed it. RM-51 rejected
  RM-50 under Option C; RM-52 prepared the offline closure packet and
  prioritized error backlog; RM-53 accepted offline custody only and RM-54
  accepted the revised design for RM-55 contract definition only. RM-55
  accepted the SourceVersion/source-receipt contract; RM-56 accepted the
  TextAnchor coordinate contract; RM-57 accepted the per-item
  validation/quarantine boundary; RM-58 accepted the confirmed-entity
  relation gate; RM-59 accepted deterministic relation evidence selection and
  RM-60 accepted the constrained relation contract; RM-61 accepted durable
  append-only review decision receipts; RM-62 accepted the source-first review
  workbench contract and RM-63 accepted the disabled-by-default approved-only
  assertion materialization boundary; RM-64 accepted versioned inference
  invalidation/rebuild; RM-65 accepted correction-burden telemetry; RM-66
  accepted the offline adversarial/default-path gate and RM-67 accepted the
  closed-world human correction-burden contract for RM-68 preregistration only.
  RM-68 is accepted only for the internal PoC; the historical bounded packet
  is `DRAFT_BLOCKED_EXTERNAL_CUSTODY`, not a preregistration. A
  [accepted human-first extraction framework design](sprint-plans/sprint-12/human-first-extraction-framework.v2.md)
  remains preserved historical design input; the owner-approved Sprint 13 plan
  now operationalizes its evidence-first successor. Validation, held-out access,
  remediation implementation, lineage preparation, provider execution, Stage B,
  selection, and promotion remain closed. No business-quality claim is made.
  The dense-hard R1--R5 concerns are mapped into Sprint 13; R6/R7 and any fresh
  evaluation remain closed pending a separate owner decision. The authoritative
  dashboard is the [Sprint 12 current-state index](sprint-plans/sprint-12/current-state.md).*

## Planned Sprints

- **Sprint 15+ / post-Sprint-14:** Decide `1.0.0` release readiness only after
  Sprint 14's direct user experience gate, remaining corrections, security,
  data migration/recovery and supported-platform evidence, with explicit
  owner release approval. Governed outbound actions, continuous synchronization,
  additional connectors, broader tenant administration, managed adapters or HA
  remain future choices based on measured bottlenecks and approved value.

## Backlog / Future Work

- Teams live tenant acceptance, Outlook/Jira, authenticated GitHub, and later
  connectors; GitHub Public Issues is the Sprint 11 read-only release target.
- Broader RBAC/ABAC and tenant administration beyond Sprint 11's minimal
  server-owned project membership and finite capabilities.
- Managed storage, backup/restore drills và production observability.
- Search engine hoặc event broker khi PostgreSQL-based baseline không còn đáp ứng.
- Dense-hard R1--R5 concerns are mapped into Sprint 13's human-first design;
  R6/R7 and any fresh evaluation remain closed pending a separate owner
  decision. Do not tune or rerun frozen candidates or reuse frozen
  source/gold/candidate evidence.
- Tauri desktop companion, native keyring, tray/global shortcut và offline draft
  chỉ khi có requirement native hoặc local-first cụ thể; desktop không đóng gói
  lại backend Compose mặc định.
