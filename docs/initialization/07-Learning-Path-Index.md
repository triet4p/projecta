# Learning Path Index

## 1. Mục tiêu

Lộ trình học được map trực tiếp với việc xây sản phẩm. Không học toàn bộ lý thuyết trước rồi mới code; mỗi nhóm kiến thức phải tạo ra artifact hoặc vertical slice trong hệ thống.

---

## 2. Mức độ kiến thức

| Mức | Ý nghĩa |
|---|---|
| Awareness | Hiểu khái niệm và biết khi nào dùng |
| Working | Tự triển khai use case cơ bản |
| Proficient | Thiết kế, debug và review production code |
| Deep | Tối ưu, mở rộng framework hoặc xử lý edge case khó |

---

## 3. Learning Map

| Chủ đề | Mức cần đạt | Áp dụng vào dự án |
|---|---:|---|
| RDF và Turtle | Proficient | Domain data model |
| RDFS | Proficient | Class/property hierarchy |
| OWL 2 practical subset | Working–Proficient | Semantics và inference |
| SPARQL 1.1 | Proficient | Query, update, named graph |
| SHACL Core | Proficient | Data validation |
| SHACL-SPARQL | Working | Cross-entity constraints |
| Apache Jena | Proficient | Semantic Core |
| Fuseki/TDB2 | Working–Proficient | RDF persistence/API |
| Jena Rule Engine | Working | Business inference |
| PROV-O | Working | Evidence/provenance |
| Ontology engineering | Proficient | Competency questions, modularization |
| Temporal knowledge modeling | Working | Requirement evolution |
| Knowledge graph testing | Proficient | Regression and competency tests |
| FastAPI/Pydantic | Proficient | Main API và contracts |
| Java/Kotlin service | Working | Semantic Core implementation |
| PostgreSQL | Proficient | Operational state |
| Event-driven architecture | Working–Proficient | Connector/event pipeline |
| OAuth 2.0/OIDC | Working | Connector and user auth |
| Webhook/idempotency | Proficient | Reliable connector ingestion |
| RBAC/ABAC | Working | Project and action policy |
| LLM structured extraction | Proficient | Candidate generation |
| Entity resolution | Working–Proficient | Link external mentions to graph |
| Hybrid retrieval | Working | Graph + text + vector |
| LLM evaluation | Working | Accuracy and grounding |
| OpenTelemetry | Working | Trace semantic lifecycle |
| Docker/Compose | Working–Proficient | Local, CI và early production deployment |
| Kubernetes | Awareness–Working | Scale-out production khi có requirement |

---

## 4. Build-and-Learn Sequence

## Phase 1 — Semantic Foundations

### Học

- RDF triple.
- IRI, literal, blank node.
- Turtle và TriG.
- RDFS class/property.
- SPARQL SELECT, CONSTRUCT, ASK.
- Named graphs.
- Protégé cơ bản.

### Xây

- Core ontology.
- Project, Person, Note, Requirement, Task, Question.
- Sample project graph.
- 10–15 competency questions.
- SPARQL tests.

### Deliverable

```text
ontology/core.ttl
ontology/examples/project-demo.trig
ontology/competency-questions/
```

---

## Phase 2 — Validation and Knowledge Lifecycle

### Học

- SHACL Core.
- SHACL-SPARQL.
- Open-world vs closed-world.
- Candidate/asserted/inferred separation.
- PROV-O.

### Xây

- TaskShape.
- RequirementShape.
- CandidateEvidenceShape.
- Cross-project constraint.
- Candidate confirmation flow.
- Provenance graph.

### Deliverable

```text
Quick Note
→ Candidate RDF
→ SHACL Report
→ Confirmed Assertion
```

---

## Phase 3 — Apache Jena Semantic Core

### Học

- Jena Dataset.
- Fuseki endpoints.
- TDB2 transactions.
- Jena SHACL API.
- ARQ.
- Jena rule syntax.
- Derivation logging.

### Xây

- Java/Kotlin Semantic Core service.
- `validate`, `confirm`, `reject`, `query`, `reason` APIs.
- Named graph router.
- Inference materializer.
- RDF transaction tests.

### Deliverable

Chạy semantic lifecycle thật trên Fuseki/TDB2.

---

## Phase 4 — Operational Infrastructure

### Học

- PostgreSQL transaction.
- Alembic.
- Outbox/inbox pattern.
- Idempotency.
- Retry/DLQ.
- Workflow state machine.
- Object storage.

### Xây

- Connector installation.
- Raw source persistence.
- Workflow run.
- Candidate review state.
- Audit index.
- Projection refresh.

### Deliverable

Một event được ingest an toàn, không duplicate và có thể replay.

---

## Phase 5 — Evidence-first Assisted Authoring

### Học

- Human-authored structured capture.
- Bounded local suggestions on demand.
- JSON Schema.
- Server-owned SourceVersion/TextAnchor and evidence selection.
- Ontology-constrained classification.
- Explicit review receipts and candidate lifecycle.
- Cost budgets, cache/dedup and zero-model fallback.
- Prompt/version evaluation.
- Model gateway abstraction.

### Xây

- Human occurrence/entity capture slice.
- One-item suggestion workflow.
- Relation-on-demand after confirmed endpoints.
- Mutation/adversarial contract tests.

### Deliverable

```text
Human task/question or structured note
→ scoped evidence
→ confirmed occurrence/entity
→ optional bounded suggestion
→ human receipt
→ approved-only RDF
```

---

## Phase 6 — Retrieval and Question Answering

### Học

- SPARQL query planning.
- Full-text search.
- Embedding.
- Hybrid retrieval.
- Reranking.
- Grounded answer generation.

### Xây

- Project-scoped search.
- Entity lookup.
- Requirement history query.
- Blocker query.
- Evidence-backed answer.
- Query template registry.

### Deliverable

Agent trả lời competency questions kèm source và knowledge status.

---

## Phase 7 — Connector Framework

### Học

- Connector adapter pattern.
- Canonical event schema.
- OAuth 2.0/OIDC.
- Webhook verification.
- Incremental sync.
- Cursor.
- Rate limit.
- Capability matrix.

### Xây

- Mock connector.
- Manual note connector.
- Teams connector.
- Outlook connector.
- Action router.

### Deliverable

Cùng một semantic pipeline nhận dữ liệu từ hai connector khác nhau.

---

## Phase 8 — Agent Workflows

### Học

- Tool calling.
- Planner vs deterministic workflow.
- Policy-controlled action.
- Human approval.
- Agent evaluation.
- Prompt injection boundaries.

### Xây

- Prepare meeting brief.
- Research topic.
- Review blockers.
- Draft project update.
- Send approved message.
- Explain inference.

### Deliverable

Một workflow end-to-end sử dụng graph, rules, evidence và connector.

---

## Phase 9 — Security, Governance and Production

### Học

- Tenant isolation.
- RBAC/ABAC.
- Secret management.
- Audit.
- Data retention.
- Backup/recovery.
- OpenTelemetry.
- Threat modeling.

### Xây

- Project permission.
- Action policy.
- Model routing policy.
- End-to-end tracing.
- Backup and restore.
- Production deployment.

### Deliverable

Production readiness review.

---

## 5. Recommended Learning Depth by Role

### Python application side

Cần sâu:

- FastAPI.
- Pydantic.
- PostgreSQL.
- Workflow.
- Connector reliability.
- LLM gateway.
- Evaluation.

### Semantic Core side

Cần sâu:

- RDF.
- SPARQL.
- SHACL.
- Jena.
- Ontology versioning.
- Rule engine.
- Provenance.

### Không cần học quá sâu ngay

- Full OWL 2 DL theorem proving.
- Tự viết triple store.
- Tự viết embedding model.
- Multi-agent swarm.
- Distributed graph algorithm.
- Custom Kubernetes operator.

Chỉ học sâu khi competency question hoặc production constraint yêu cầu.

---

## 6. Weekly Learning Loop

Mỗi chu kỳ:

1. Chọn một competency question.
2. Bổ sung ontology vừa đủ.
3. Viết SHACL.
4. Tạo test data.
5. Viết SPARQL.
6. Implement service.
7. Thêm evaluation.
8. Demo vertical slice.
9. Ghi architecture decision record.

Không học một chủ đề mà không có artifact áp dụng vào dự án.

---

## 7. Suggested First Vertical Slice

### Use case

BrSE nhập:

> Khách muốn dashboard cập nhật mỗi 30 phút. Nam kiểm tra khả năng đáp ứng trước thứ Sáu. Chưa rõ retention period.

### Hệ thống phải tạo

- Requirement candidate.
- Task candidate.
- Question candidate.
- Assignee candidate.
- Due-date candidate.
- Evidence span.
- Semantic relations.
- SHACL report.
- Review UI.
- Asserted graph sau xác nhận.
- Inference nếu task bị block.
- Provenance.

Vertical slice này bao phủ:

```text
RDF
→ OWL
→ SHACL
→ SPARQL
→ Jena
→ LLM extraction
→ Human confirmation
→ Provenance
→ Rule inference
```

Đây là điểm bắt đầu phù hợp nhất vì sử dụng toàn bộ core architecture mà chưa phụ thuộc quyền Teams.
