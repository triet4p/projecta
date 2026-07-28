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

- [ ] **M1 — Executable Semantic Foundation (Sprints 1–3):** Ontology kernel, SHACL/provenance lifecycle và Jena Semantic Core chạy thật.
- [ ] **M2 — Manual Quick Note Slice (Sprint 4):** Note → candidate → review → assertion → inference qua API tối thiểu.
- [ ] **M3 — LLM Extraction and Evaluation (Sprint 5):** Structured candidate extraction có evidence và evaluation dataset.
- [ ] **M4 — Retrieval and Coordination (Sprint 6):** Project-scoped queries, requirement history, blockers và evidence-backed answers.
- [ ] **M5 — Connector and Production Evolution (Sprint 7+):** Mock/manual framework, connector thật đầu tiên, security và operational hardening.

## Active Sprints

- None.

## Completed Sprints

- [Sprint 1 — Ontology Kernel](sprint-plans/sprint-1.md) — *Completed
  2026-07-28; ontology v0.1 approved and validated.*

## Planned Sprints

- **Sprint 2:** SHACL, candidate/asserted/inferred separation, provenance và temporal assertions.
- **Sprint 3:** Jena Semantic Core APIs, TDB2/Fuseki Compose service và transaction tests.
- **Sprint 4:** Manual Quick Note API, deterministic candidates và human review flow.
- **Sprint 5:** Provider-agnostic LLM extraction, entity linking và evaluation.
- **Sprint 6:** Semantic retrieval, rules, projections và grounded response.

## Backlog / Future Work

- Teams/Outlook/Jira connectors.
- Authentication, RBAC/ABAC và tenant administration.
- Managed storage, backup/restore drills và production observability.
- Search engine hoặc event broker khi PostgreSQL-based baseline không còn đáp ứng.
