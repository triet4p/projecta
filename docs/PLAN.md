# Projecta Global Plan

## Overview

Xây Projecta theo các vertical slice có thể kiểm chứng, bắt đầu từ Quick Note thủ công và semantic lifecycle. Ontology đi trước từng slice như domain contract, nhưng mỗi increment phải đi kèm dữ liệu mẫu, competency query và automated validation; không thiết kế toàn bộ ontology trước khi có use case.

## Planning Principles

- Mỗi term/rule mới phải phục vụ competency question hoặc governance requirement.
- Mỗi semantic change đi qua `$projecta-evolve-ontology` và human approval.
- Ưu tiên đường chạy end-to-end nhỏ hơn infrastructure breadth.
- Manual/Mock connector đi trước Teams; deterministic candidate fixture đi trước LLM.
- Không thêm Kafka, OpenSearch, Kubernetes hoặc full observability trước khi volume/SLO yêu cầu.

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
  security và production hardening.

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

## Active Sprints

- [Sprint 10 — Governed Connector Foundation and v0.5.0](sprint-plans/sprint-10.md)
  — *G2 approved; implementation, clean-checkout validation, clean-Compose
  acceptance, and isolated recovery pass. Product version `0.5.0`, the dated
  changelog section, and release contract are aligned; immutable release
  preflight is in progress. G3, tagging, and publication remain gated.*

## Planned Sprints

- **Sprint 11+:** First production connector, production authentication and
  authorization, server-side secret-manager integration, outbound actions, and
  broader production hardening after the Sprint 10 connector contract is
  accepted.

## Backlog / Future Work

- Teams/Outlook/Jira connectors.
- Authentication, RBAC/ABAC và tenant administration.
- Managed storage, backup/restore drills và production observability.
- Search engine hoặc event broker khi PostgreSQL-based baseline không còn đáp ứng.
- Tauri desktop companion, native keyring, tray/global shortcut và offline draft
  chỉ khi có requirement native hoặc local-first cụ thể; desktop không đóng gói
  lại backend Compose mặc định.
