# Project Scope

## 1. Mục đích

Tài liệu này xác định ranh giới chức năng và kỹ thuật của Project Intelligence Platform. Scope được thiết kế theo hướng sản phẩm thực tế, không giản lược semantic core thành một bản demo.

---

## 2. In Scope

## 2.1. Domain knowledge management

Hệ thống quản lý các nhóm entity nghiệp vụ chính:

- Project.
- Person, Team, Organization và External Identity.
- Note và Note Item.
- Requirement.
- Decision.
- Question.
- Assumption.
- Constraint.
- Risk.
- Task.
- Milestone.
- Deliverable.
- Progress Claim.
- Research Question và Research Finding.
- Document và Source Artifact.
- Message, Conversation và Communication Channel.

Các entity được liên kết bằng quan hệ semantic có type, provenance, temporal validity và verification status.

---

## 2.2. Ontology-driven semantic core

Bao gồm:

- RDF data model.
- OWL/RDFS ontology.
- SHACL validation.
- Named graph strategy.
- Candidate, asserted và inferred graph.
- Business inference rules.
- PROV-O provenance.
- Ontology versioning và migration.
- SPARQL query/update.
- Competency-question-driven ontology design.

Đây là core architecture, không phải tính năng tùy chọn.

---

## 2.3. Quick Note workflow

- Tạo note theo project.
- Hỗ trợ note chứa nhiều đoạn hoặc nhiều loại nội dung.
- Tách note thành atomic note items.
- Gợi ý requirement, task, decision, question, risk hoặc assumption.
- Chọn evidence span.
- Gợi ý liên kết với entity hiện có.
- Review, edit, confirm hoặc reject candidate.
- Ghi provenance khi candidate được xác nhận.

---

## 2.4. Project memory và semantic retrieval

- Truy vấn theo entity và relation.
- Theo dõi requirement evolution.
- Theo dõi dependency, blocker và impact.
- Tìm nguồn chứng minh cho fact.
- Truy xuất kết hợp graph, full-text và vector similarity.
- Tạo contextual view theo project, user và permission.
- Tách source artifact khỏi authoritative knowledge.

---

## 2.5. Agent capabilities

- Hiểu user intent.
- Chọn workflow hoặc tool.
- Truy xuất knowledge graph.
- Gợi ý entity/relation candidate.
- Entity linking.
- Research planning.
- Soạn meeting brief.
- Soạn project update.
- Soạn clarification questions.
- Soạn task description và acceptance criteria.
- Soạn message hoặc email.
- Giải thích inference và recommendation bằng evidence.

Agent không được bỏ qua policy, SHACL hoặc confirmation workflow.

---

## 2.6. Connector framework

Connector là abstraction độc lập với semantic core.

Connector framework bao gồm:

- Inbound event ingestion.
- Outbound action execution.
- Capability declaration.
- Identity mapping.
- OAuth/token metadata.
- Webhook hoặc polling.
- Incremental sync.
- Cursor management.
- Idempotency.
- Retry và dead-letter handling.
- External resource linking.

Connector ưu tiên ban đầu:

1. Manual/Quick Note connector.
2. JSON/Mock connector.
3. Microsoft Teams.
4. Outlook/email.
5. Work-management connector như Jira, Azure DevOps hoặc Planner.

Slack, Zalo và các connector khác được hỗ trợ qua cùng contract khi có yêu cầu.

---

## 2.7. Operational infrastructure

- Authentication và authorization.
- Tenant and project isolation.
- Connector installation state.
- Agent run và workflow run.
- Job, retry, timeout và idempotency.
- Audit log.
- Secret references.
- Event outbox/inbox.
- Read projections và cache.
- Observability.

---

## 2.8. Data stores

- RDF triple store cho semantic source of truth.
- PostgreSQL cho operational state và read projection.
- Object storage cho raw payload, attachment và file.
- Search/vector index cho retrieval.
- Git cho ontology, SHACL, rules và migration artifacts.

---

## 2.9. Human-in-the-loop

Bắt buộc hỗ trợ:

- Xác nhận candidate knowledge.
- Sửa entity hoặc relation trước khi assertion.
- Duyệt outbound action có rủi ro.
- Phân biệt AI suggestion, inferred fact và human-confirmed fact.
- Audit người đã xác nhận hoặc sửa.

---

## 2.10. Security and governance

- Least-privilege connector access.
- Project-scoped retrieval.
- Tenant isolation.
- Source-level provenance.
- Action policy.
- Sensitive data handling.
- Retention metadata.
- Auditability.
- Model-provider abstraction để hỗ trợ local model hoặc private deployment khi cần.

---

## 3. Out of Scope

## 3.1. Transcript-first meeting intelligence

Không xây hệ thống quanh meeting transcript.

Không bao gồm:

- Bắt buộc record/transcribe meeting.
- Tự động phân tích toàn bộ transcript làm nguồn requirement chính.
- Tự động kết luận decision chỉ từ transcript.
- Thay thế trách nhiệm diễn giải requirement của BrSE.

Transcript có thể được thêm sau như một source artifact bình thường nếu tổ chức yêu cầu, nhưng không thay đổi kiến trúc cốt lõi.

---

## 3.2. Thay thế hoàn toàn hệ thống task management

Sản phẩm không nhằm thay thế toàn bộ:

- Jira.
- Azure DevOps.
- Microsoft Planner.
- GitHub Issues.
- Các quy trình sprint hoặc release management hiện có.

Hệ thống duy trì semantic view và coordination intelligence, đồng thời đồng bộ với task system khi cần.

---

## 3.3. Tự động hóa không kiểm soát

Không cho phép LLM tự:

- Giao task chính thức.
- Thay đổi deadline.
- Chuyển task sang Done.
- Thay đổi requirement.
- Gửi nội dung cho khách hàng.
- Truy cập dữ liệu ngoài permission.
- Tạo predicate hoặc ontology class mới trong production.

Các hành động này phải qua policy, deterministic service và approval phù hợp.

---

## 3.4. General-purpose enterprise search

Sản phẩm không phải công cụ tìm kiếm cho toàn bộ tài liệu doanh nghiệp. Retrieval luôn gắn với:

- Project scope.
- Domain ontology.
- User permission.
- Workflow cụ thể.

---

## 3.5. Full BI platform

Sản phẩm có thể hỗ trợ:

- Gợi ý KPI.
- Data requirement.
- Dashboard specification.
- Wireframe hoặc mock description.
- Draft SQL/DAX.

Nhưng không nhằm thay thế Power BI, Tableau hoặc nền tảng data warehouse.

---

## 3.6. Universal connector coverage ngay lập tức

Kiến trúc phải connector-agnostic từ đầu, nhưng không cần triển khai mọi connector cùng lúc.

Việc tăng dần connector là chiến lược delivery, không phải giản lược semantic core.

---

## 3.7. Full autonomous multi-agent organization

Không ưu tiên:

- Nhiều agent tự giao tiếp không kiểm soát.
- Agent tự phân chia quyền lực hoặc mục tiêu.
- Swarm orchestration phức tạp.
- Hành động liên hệ khách hàng hoàn toàn tự động.

Agent roles có thể được tách logic, nhưng vẫn vận hành trong workflow và policy rõ ràng.

---

## 4. Boundary Decisions

| Chủ đề | Quyết định |
|---|---|
| Teams | Connector đầu tiên, không phải system center |
| LLM | Top-level intelligence interface, không phải source of truth |
| Ontology | Core domain model |
| RDF store | Semantic source of truth |
| PostgreSQL | Operational state và projection |
| Vector DB | Retrieval aid, không phải project truth |
| Raw messages | Evidence/source artifact |
| Task status | Authoritative trong semantic domain hoặc external task system được liên kết |
| Human approval | Bắt buộc tại điểm tạo assertion hoặc hành động rủi ro |
| Transcript | Không thuộc core workflow |
| Connector rollout | Incremental theo permission và business need |
| Core architecture | Không được cắt giảm dưới danh nghĩa MVP |

---

## 5. Delivery Scope Strategy

Delivery tăng dần theo vertical slice nhưng mỗi slice phải sử dụng kiến trúc lõi thật.

Ví dụ slice đầu tiên:

```text
Quick Note
→ Canonical Source Artifact
→ LLM Candidate Extraction
→ SHACL Validation
→ Human Confirmation
→ Asserted RDF
→ Rule Inference
→ Project Context Query
```

Slice tiếp theo có thể thay Quick Note bằng Teams message nhưng không thay đổi semantic lifecycle.

Điểm có thể mock:

- External connector.
- OAuth flow.
- Webhook delivery.
- Tenant admin consent.
- External task-system write action.

Điểm không được mock về mặt kiến trúc:

- Ontology.
- Named graph separation.
- Provenance.
- Validation.
- Candidate lifecycle.
- Permission contract.
- Semantic query.
