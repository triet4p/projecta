# Tech Stack

## 1. Nguyên tắc lựa chọn

- Python là ngôn ngữ chính cho application, agent và connector orchestration.
- Java hoặc Kotlin dùng cho Semantic Core dựa trên Apache Jena.
- RDF/OWL/SHACL/SPARQL là semantic stack.
- PostgreSQL giữ operational state.
- Connector và LLM đều thông qua abstraction.
- Mọi thành phần core phải production-oriented về kiến trúc, dù external integration có thể được triển khai tăng dần.

---

## 2. Application and API

| Thành phần | Công nghệ đề xuất | Vai trò |
|---|---|---|
| Main backend | Python 3.12+ | Application service, workflow, connector orchestration |
| API framework | FastAPI | REST API, async endpoints, typed contracts |
| Validation | Pydantic | Canonical events, tool schemas, LLM structured output |
| Dependency management | uv hoặc Poetry | Reproducible environment |
| Testing | pytest, hypothesis | Unit, integration, property-based tests |
| Type checking | mypy hoặc pyright | Contract safety |
| Lint/format | Ruff | Code quality |

---

## 3. Semantic Core

| Thành phần | Công nghệ |
|---|---|
| Language | Java 21 hoặc Kotlin |
| Framework | Spring Boot hoặc lightweight Javalin/Quarkus |
| RDF framework | Apache Jena |
| SPARQL server | Fuseki |
| Persistent RDF store | TDB2 |
| Validation | Jena SHACL |
| Reasoning | Jena Generic Rule Reasoner |
| Ontology editing | Protégé |
| Serialization | Turtle, TriG, JSON-LD |
| Provenance | PROV-O |

Semantic Core chịu trách nhiệm:

- Validate.
- Promote candidate.
- Update asserted graph.
- Materialize inference.
- Record provenance.
- Enforce graph routing.
- Expose domain-safe semantic APIs.

Python không gửi arbitrary SPARQL update trực tiếp vào asserted graph.

---

## 4. Operational Data

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| RDBMS | PostgreSQL | Auth metadata, connector state, workflow, retry, projection |
| ORM | SQLAlchemy 2.x | Python operational persistence |
| Migration | Alembic | Database migration |
| Cache/lock | Redis | TTL session, short lock, rate-limit cache |
| Secrets | Azure Key Vault, Vault hoặc cloud secret manager | Token và credential thật |

---

## 5. Object and File Storage

| Môi trường | Công nghệ |
|---|---|
| Local/self-hosted | MinIO |
| Azure | Azure Blob Storage |
| AWS-compatible | S3 |

Lưu:

- Raw connector payload.
- Attachment.
- Document.
- Research snapshot.
- Export artifact.
- Large evidence content.

RDF chỉ giữ metadata, URI và provenance.

---

## 6. Search and Vector Retrieval

Lựa chọn ưu tiên:

### Option A

- OpenSearch.
- Full-text + vector search.
- Entity IRI làm document key.

### Option B

- PostgreSQL + pgvector.
- Phù hợp khi quy mô chưa yêu cầu search cluster riêng.

Retrieval pipeline kết hợp:

```text
SPARQL filtering
+ keyword search
+ vector similarity
+ LLM reranking
```

Không dùng vector index làm source of truth.

---

## 7. Event and Workflow Infrastructure

| Thành phần | Công nghệ đề xuất |
|---|---|
| Event contract | Canonical event schema bằng Pydantic/JSON Schema |
| Message broker | Kafka hoặc Redpanda |
| Outbox/inbox | PostgreSQL transactional outbox |
| Workflow orchestration | Temporal hoặc custom state machine |
| Background jobs | Temporal worker hoặc Celery/Dramatiq nếu scope nhỏ hơn |
| Retry/DLQ | Broker + PostgreSQL metadata |

Khuyến nghị:

- Dùng event contract ngay từ đầu.
- Broker có thể được đưa vào khi connector/event volume yêu cầu.
- Outbox pattern giữ tính nhất quán giữa operational DB và event publication.

---

## 8. LLM and Agent Layer

| Thành phần | Công nghệ |
|---|---|
| LLM abstraction | Custom `LLMGateway` |
| Structured output | JSON Schema/Pydantic |
| Tool orchestration | Custom typed tools; có thể dùng LangGraph nếu phù hợp |
| Prompt/version tracking | Git + database metadata |
| Evaluation | pytest datasets, custom metrics, Langfuse/OpenTelemetry |
| Model providers | OpenAI, Azure OpenAI, Anthropic, Gemini hoặc local model |
| Local serving | vLLM/Ollama khi cần dữ liệu riêng tư |

Không bind domain module trực tiếp vào SDK của một provider.

---

## 9. Connector Layer

### Contract

```python
class Connector:
    async def pull_events(self, cursor: str | None): ...
    async def handle_webhook(self, payload: bytes): ...
    async def fetch_resource(self, external_id: str): ...
    async def resolve_identity(self, external_user_id: str): ...
    async def execute_action(self, action): ...
    def capabilities(self): ...
```

### Connector implementations

| Connector | Công nghệ/API |
|---|---|
| Microsoft Teams | Microsoft Graph, Teams app/bot SDK |
| Outlook | Microsoft Graph Mail API |
| Slack | Slack Web API + Events API |
| Jira | Jira REST API |
| Azure DevOps | Azure DevOps REST API |
| Google Drive | Google Drive API |
| Zalo | Adapter theo API khả dụng và policy của nền tảng |
| Manual/Quick Note | Native application API |

Connector mapping không chứa ontology reasoning.

---

## 10. Frontend

| Thành phần | Công nghệ |
|---|---|
| Web app | React + TypeScript static SPA |
| Build/dev tool | Vite |
| UI components | shadcn/ui hoặc component system nội bộ |
| API client | Generated TypeScript client from versioned Application API snapshot |
| Data fetching | TanStack Query |
| Forms | React Hook Form + Zod |
| Auth/context | Server-established experience context; OIDC-compatible client deferred |

Sprint 7 uses the web app as the canonical interaction surface. The static
assets are served through the Compose web boundary and call only the FastAPI
Application API over the documented same-origin route. The browser never calls
Semantic Core or Fuseki directly. Tauri is reserved for a future thin desktop
wrapper that reuses this client and calls the same server API; it does not
package Python, Java, Fuseki, or operational storage.

Sprint 7 screens:

- Application shell and local-experience status.
- LLM settings and connection check.
- Quick Note extraction and manual typed capture.
- Candidate validation/review with Requirement-only confirmation.
- Knowledge, history, and evidence views.
- Bounded grounded project Q&A.
- Experience diagnostics, limited to local-mode operations.

Project dashboard, connector settings, graph visualization, full audit
inspector, and OIDC authentication remain future capabilities unless a later
sprint adds their contracts.

---

## 11. Security

- OIDC/OAuth 2.0.
- RBAC kết hợp project membership.
- ABAC cho resource sensitivity và action type.
- Tenant isolation.
- Encrypted secrets.
- Signed webhook verification.
- Audit trail.
- Model routing policy.
- Data-retention metadata.
- Least-privilege connector scopes.

Có thể dùng Keycloak cho self-hosted identity hoặc Microsoft Entra ID trong môi trường Microsoft-centric.

---

## 12. Observability

| Thành phần | Công nghệ |
|---|---|
| Tracing | OpenTelemetry |
| Metrics | Prometheus |
| Dashboard | Grafana |
| Logs | Loki hoặc OpenSearch |
| LLM trace | Langfuse hoặc custom OpenTelemetry spans |
| Error tracking | Sentry |

Trace cần nối được:

```text
Connector Event
→ Candidate Extraction
→ SHACL Validation
→ Confirmation
→ RDF Update
→ Rule Inference
→ Outbound Action
```

---

## 13. Deployment

### Local development

- Docker Compose là baseline cho service topology và infrastructure dependency.
- PostgreSQL/pgvector và Fuseki/TDB2 chạy bằng container mặc định.
- Object storage, Redis, observability và search engine riêng được bật bằng Compose profile khi cần.
- Python API, Java/Kotlin Semantic Core và frontend có thể:
  - Chạy trên host để có inner loop và debugger nhanh.
  - Chạy trong container để kiểm tra integration và production image.
- Dùng multi-stage Dockerfile với các target `dev`, `test` và `runtime`.
- Dùng Compose Watch hoặc framework-native hot reload; thay đổi dependency phải rebuild image.
- Không yêu cầu local Kubernetes trong workflow hằng ngày.

### Early production

- Một Linux VM chạy Docker Engine và Docker Compose.
- Deploy đúng immutable OCI image đã được CI build và test; không build source trên production.
- Dùng `compose.prod.yaml` để override restart policy, resource limit, logging, network exposure và production configuration.
- Reverse proxy/TLS đặt trước web/API.
- Persistent volume cho PostgreSQL và Fuseki/TDB2.
- Secret thật được inject từ secret store hoặc deployment environment, không nằm trong image hoặc Git.
- Backup off-host và restore test cho TDB2, PostgreSQL và object storage.
- Fuseki/TDB2 có một owner process; không scale ngang bằng cách cho nhiều container cùng mount một database directory.

### Scale-out production

- Chuyển PostgreSQL và object storage sang managed service trước khi tăng orchestration complexity.
- Kubernetes/Helm chỉ được đưa vào khi có yêu cầu cụ thể về high availability, autoscaling, nhiều environment hoặc quy mô vận hành.
- Stateless service có thể scale ngang; RDF store cần chiến lược stateful riêng.
- Local development vẫn dùng Compose; Kubernetes manifest được kiểm tra ở CI/staging.
- Việc đổi deployment substrate không được thay đổi application contract, ontology lifecycle hoặc policy boundary.

Chi tiết quyết định và parity rules nằm trong `08-Deployment-Choice.md`.

---

## 14. Repository structure

```text
projecta/
├── compose.yaml
├── compose.dev.yaml
├── compose.prod.yaml
├── .env.example
├── apps/
│   ├── web/
│   │   └── Dockerfile
│   └── api/
│       └── Dockerfile
├── services/
│   ├── semantic-core/
│   │   └── Dockerfile
│   ├── agent-orchestrator/
│   │   └── Dockerfile
│   └── action-router/
│       └── Dockerfile
├── connectors/
│   ├── manual/
│   ├── mock/
│   └── workers/
│       └── Dockerfile
├── ontology/
│   ├── shapes/
│   ├── rules/
│   ├── examples/
│   ├── competency-questions/
│   └── migrations/
├── schemas/
├── infra/
│   ├── docker/
│   │   ├── fuseki/
│   │   ├── reverse-proxy/
│   │   └── observability/
│   ├── env/
│   └── kubernetes/          # Chỉ thêm khi có scale-out decision
├── scripts/
├── .agents/
│   ├── memory/
│   └── skills/
│       └── projecta-evolve-ontology/
├── docs/
├── evaluation/
└── test-data/
```

Quy ước:

- Dockerfile đặt cạnh build context của application service.
- `compose.yaml` định nghĩa topology và cấu hình chung.
- `compose.dev.yaml` chỉ chứa local override như port, watch, debug và seed data.
- `compose.prod.yaml` chỉ chứa production override; service dùng image digest/tag do CI cung cấp.
- Cấu hình image dùng chung như Fuseki và reverse proxy nằm trong `infra/docker`.
- Skill đặc thù của Projecta được version cùng repository trong `.agents/skills/`.
- Không duy trì thêm một bản cài global trong `C:\Users\admin\.codex\skills`; tránh hai source bị lệch và bảo đảm skill đi cùng version tài liệu/ontology của dự án.
- Không commit `.env`, secret, token hoặc production credential.

---

## 15. Chốt stack

```text
Primary language: Python
Semantic language: Java/Kotlin
Frontend: TypeScript/React
Semantic store: Apache Jena Fuseki + TDB2
Ontology: RDF + OWL
Validation: SHACL
Query: SPARQL
Reasoning: Jena Rules
Operational DB: PostgreSQL
Raw files: MinIO/Azure Blob/S3
Search: OpenSearch hoặc pgvector
Events: PostgreSQL Outbox trước; Kafka/Redpanda khi volume yêu cầu
LLM: Provider-agnostic gateway
Local deployment: Docker Compose
Early production: Docker Compose trên Linux VM
Scale-out production: Managed services + Kubernetes khi có nhu cầu
```
