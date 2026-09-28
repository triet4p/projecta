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
  remains open; sequencing of additional connector/outbound breadth follows the
  active Sprint 13 evidence-first authoring slice and measured bottlenecks.
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
  selection, promotion, or release claim follows. Sprint 12 is now historical
  and closed for the active product direction; Sprint 13 is its successor.

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

## Active Sprint

- [Sprint 13 — Evidence-first Assisted Authoring](sprint-plans/sprint-13.md)
  — *Real Docker browser-to-live-backend capture, review, relation and
  PostgreSQL receipt flows passed the S13-07 evidence gate. The optional
  local-model Compose boundary and fail-closed runtime errors passed the
  corrected S13-07 gate. Receipt and relation error handling passed their
  corrected task gates; sprint-wide differential re-review remains pending.
  Offline evaluation/R6/R7 remain deferred, production materialization remains
  locked, and the owner-waived project graph remains stale.*

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

- **Sprint 14+:** Select from Sprint 13 measured authoring friction and approved
  business value. Resume governed outbound actions, continuous synchronization,
  additional connectors, broader tenant administration, managed adapters, or HA
  only when the measured bottleneck justifies that work.

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
