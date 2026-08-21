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
  remains open, but additional connector/outbound breadth is paused until the
  Sprint 12 business-quality evidence is reviewed.
- [~] **M8 — Business Semantic Quality and Evaluation (Sprint 12):** Governed
  atomic and longitudinal datasets, leakage-resistant splits,
  ontology/graph/retrieval metrics, controlled optimization, sealed held-out
  evaluation, and target-role business acceptance. The historical synthetic
  corpus and rejected prompt experiments are retained as evidence. G3.1-A/B/C
  are complete with scope limits; M8 is now at the exact f12 two-step package
  with one bounded development Stage A execution authorized and not yet run.

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

## Active Sprints

- [Sprint 12 — Business Semantic Quality and Evaluation](sprint-plans/sprint-12.md)
  — *In progress at `G5_F12_STAGE_A_COMPLETED_REJECTED_HARD_GATE_PENDING_OWNER_DECISION`.
  Dataset v3,
  measurement remediation and the two-step f12 development execution package
  are frozen. RM-23F issued the preregistration/freeze and RM-25 authorized one
  exact 144-call development Stage A execution after independent owner review;
  the immutable report is schema-valid but rejected by hard, threshold and
  slice gates. Retry, overwrite, validation, held-out access, Stage B,
  selection and promotion remain closed pending a separate owner post-run
  decision.
  No business-quality claim is made, and new connector/outbound breadth remains
  deferred. The authoritative dashboard is the
  [Sprint 12 current-state index](sprint-plans/sprint-12/current-state.md).*

## Planned Sprints

- **Sprint 13+:** Selected from Sprint 12 evidence. Resume governed outbound
  actions, continuous synchronization, additional connectors, broader tenant
  administration, managed adapters, or HA only when the measured business
  bottleneck justifies that work.

## Backlog / Future Work

- Teams live tenant acceptance, Outlook/Jira, authenticated GitHub, and later
  connectors; GitHub Public Issues is the Sprint 11 read-only release target.
- Broader RBAC/ABAC and tenant administration beyond Sprint 11's minimal
  server-owned project membership and finite capabilities.
- Managed storage, backup/restore drills và production observability.
- Search engine hoặc event broker khi PostgreSQL-based baseline không còn đáp ứng.
- Tauri desktop companion, native keyring, tray/global shortcut và offline draft
  chỉ khi có requirement native hoặc local-first cụ thể; desktop không đóng gói
  lại backend Compose mặc định.
