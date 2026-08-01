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
- [ ] **M3 — LLM Extraction and Evaluation (Sprint 5):** Structured candidate extraction có evidence và evaluation dataset.
- [ ] **M4 — Retrieval and Coordination (Sprint 6):** Project-scoped queries, requirement history, blockers và evidence-backed answers.
- [ ] **M5 — Connector and Production Evolution (Sprint 7+):** Mock/manual framework, connector thật đầu tiên, security và operational hardening.

## Completed Sprints

- [Sprint 1 — Ontology Kernel](sprint-plans/sprint-1.md) — *Completed
  2026-07-28; ontology v0.1 approved and validated.*
- [Sprint 2 — Governed Knowledge Lifecycle](sprint-plans/sprint-2.md) —
  *Completed 2026-07-29; ontology v0.2 approved with 73/73 checks passing.*
- [Sprint 3 — Executable Semantic Core](sprint-plans/sprint-3.md) — *Completed
  2026-07-30; Fuseki-backed runtime and M1 human-approved.*
- [Sprint 4 — Manual Quick Note Slice](sprint-plans/sprint-4.md) — *Completed
  2026-08-01; M2 and ontology v0.3.0 human-approved and released.*

## Planned Sprints

- **Sprint 5:** Provider-agnostic LLM extraction, entity linking và evaluation.
- **Sprint 6:** Semantic retrieval, rules, projections và grounded response.

## Backlog / Future Work

- Teams/Outlook/Jira connectors.
- Authentication, RBAC/ABAC và tenant administration.
- Managed storage, backup/restore drills và production observability.
- Search engine hoặc event broker khi PostgreSQL-based baseline không còn đáp ứng.
