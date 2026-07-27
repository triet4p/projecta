# Deployment Choice

## 1. Status

```text
Status: Approved
Date: 2026-07-27
Decision: Container-first, Docker Compose-first, not Kubernetes-first
```

Tài liệu này chốt deployment baseline cho Projecta. Quyết định áp dụng cho local development, CI, early production và hướng scale-out về sau.

---

## 2. Context

Projecta là một hệ thống polyglot và có nhiều stateful dependency:

- Next.js/TypeScript frontend.
- Python/FastAPI application và workflow services.
- Java hoặc Kotlin Semantic Core.
- Apache Jena Fuseki/TDB2.
- PostgreSQL/pgvector.
- Object storage.
- Redis, search engine, event broker và observability khi cần.

Nếu cài trực tiếp toàn bộ dependency trên máy developer, phiên bản và cách cấu hình dễ lệch nhau. Nếu dùng Kubernetes ngay từ đầu, chi phí tài nguyên và vận hành local cao hơn nhu cầu hiện tại, trong khi không giải quyết được đặc tính single-owner của TDB2.

Mục tiêu không phải làm local giống production 100% về topology. Mục tiêu là giữ giống nhau ở image, protocol, contract, migration và semantic behavior.

---

## 3. Decision

Projecta sử dụng:

1. OCI container cho mọi deployable application service.
2. Docker Compose làm service topology baseline cho local, integration test và early production.
3. Một Linux VM chạy Docker Engine và Compose cho production giai đoạn đầu.
4. Cùng production image được CI build và promote qua các environment.
5. Kubernetes chỉ được đưa vào khi có requirement cụ thể về availability, autoscaling hoặc operational scale.

Docker Compose là canonical workflow. Developer có thể dùng một Compose-compatible engine khác, nhưng CI phải kiểm tra bằng canonical Docker Compose configuration.

---

## 4. Environment Strategy

| Thành phần | Local | CI | Early production | Scale-out production |
|---|---|---|---|---|
| Orchestration | Docker Compose | Compose/Testcontainers | Docker Compose | Kubernetes khi cần |
| Application image | Dev target hoặc chạy host | Test/runtime target | Immutable runtime image | Cùng runtime image |
| PostgreSQL | Container | Ephemeral container | Container hoặc managed | Managed ưu tiên |
| Fuseki/TDB2 | Container + local volume | Ephemeral dataset | Một instance + persistent disk | Stateful strategy riêng |
| Object storage | S3-compatible local | Ephemeral/fake service | S3-compatible hoặc managed | Managed |
| Search | pgvector mặc định | Theo test scope | pgvector trước | OpenSearch khi volume yêu cầu |
| Event delivery | PostgreSQL outbox | Integration test | PostgreSQL outbox | Broker khi volume yêu cầu |
| Secrets | Local untracked file | CI secret | Secret injection/store | Cloud secret manager |
| Observability | Console; optional profile | Test artifacts | Structured logs/metrics | Centralized platform |

---

## 5. Compose Layout

```text
projecta/
├── compose.yaml
├── compose.dev.yaml
├── compose.prod.yaml
├── .env.example
└── infra/
    ├── docker/
    │   ├── fuseki/
    │   ├── reverse-proxy/
    │   └── observability/
    └── env/
```

### `compose.yaml`

Định nghĩa topology và cấu hình dùng chung:

- Service names và internal ports.
- Networks.
- Volumes.
- Health checks.
- Service dependency.
- Stable environment-variable contract.

### `compose.dev.yaml`

Chỉ định local override:

- Published debug ports.
- Dev image target.
- Compose Watch hoặc source synchronization.
- Framework-native hot reload.
- Seed data.
- Developer-friendly logging.

### `compose.prod.yaml`

Chỉ định production override:

- Immutable image reference.
- Restart policy.
- CPU/memory limit.
- Production logging.
- Network exposure tối thiểu.
- Reverse proxy/TLS integration.
- Không bind-mount source code.

Production configuration được tạo bằng cách merge base và production override:

```text
docker compose -f compose.yaml -f compose.prod.yaml config
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

Lệnh `config` phải chạy trong CI để phát hiện Compose configuration không hợp lệ trước deployment.

---

## 6. Compose Profiles

Default profile chỉ chứa dependency và service cần cho semantic vertical slice đầu tiên:

```text
default:
- postgres
- fuseki
- api
- semantic-core
```

Các nhóm nặng hơn được bật khi cần:

```text
frontend:
- web

storage:
- object-storage

observability:
- otel-collector
- prometheus
- grafana

scale:
- search-engine
- event-broker
```

Kafka/Redpanda, OpenSearch và full observability stack không được trở thành yêu cầu mặc định cho local development khi PostgreSQL outbox, pgvector và console logging đã đáp ứng use case.

Việc trì hoãn scale infrastructure không được phép làm giản lược:

- Ontology.
- Named graph separation.
- SHACL validation.
- Provenance.
- Candidate lifecycle.
- Permission contract.
- Semantic query.

---

## 7. Application Development Workflow

Developer có hai workflow được hỗ trợ.

### Fast inner loop

- PostgreSQL, Fuseki/TDB2 và dependency chạy trong Compose.
- Web/API/Semantic Core đang được sửa có thể chạy trực tiếp trên host.
- Service dùng cùng environment-variable contract và gọi dependency qua published local ports.

### Full integration

- Tất cả application service chạy trong Compose.
- Dùng dev Dockerfile target và Compose Watch/hot reload.
- Dùng để kiểm tra service discovery, container filesystem, health check và integration behavior.

Không được duy trì một code path riêng chỉ dành cho non-container deployment.

---

## 8. Image Strategy

Mỗi deployable service có multi-stage Dockerfile:

```text
development
→ test
→ build
→ runtime
```

Runtime image phải:

- Pin runtime và dependency version có chủ đích.
- Chạy bằng non-root user khi khả thi.
- Không chứa source-only tool, test dependency hoặc credential.
- Có health/readiness endpoint phù hợp.
- Ghi structured log ra stdout/stderr.
- Được build một lần trong CI.

Production deploy bằng image digest hoặc immutable release tag. Không SSH vào production để pull source và build tại chỗ.

---

## 9. Parity Rules

Local và production phải giống nhau ở:

- Application image lineage.
- PostgreSQL/Jena major version.
- Database migration.
- Ontology, SHACL shape và rule version.
- API và event contract.
- Environment-variable names.
- Health check.
- Startup/shutdown behavior.
- Project/tenant isolation.
- Semantic lifecycle.

Được phép khác nhau ở:

- Số replica.
- Persistent storage implementation.
- Secret provider.
- TLS termination.
- Log collection.
- Managed hay self-hosted PostgreSQL/object storage.
- Resource limit.

Một local replacement chỉ hợp lệ khi dùng cùng protocol và được che sau application abstraction. Ví dụ, local S3-compatible storage và production S3/Azure Blob phải đi qua cùng `ObjectStorage` contract.

---

## 10. Fuseki/TDB2 Constraints

TDB2 database directory chỉ có một JVM process sở hữu tại một thời điểm.

Do đó:

- Chỉ một Fuseki instance được mount database directory để ghi.
- Không scale Fuseki bằng cách cho nhiều replica cùng mount một TDB2 volume.
- Semantic Core và application service truy cập RDF qua domain-safe API/SPARQL boundary đã quy định.
- Persistent database nằm ngoài container filesystem.
- Backup phải dùng cơ chế tạo consistent view của TDB2.
- Restore phải được kiểm thử, không chỉ kiểm tra file backup tồn tại.
- Compaction và disk capacity phải có operational runbook.

Nếu scale hoặc availability requirement vượt khả năng của single-node Fuseki/TDB2, cần một architecture decision riêng cho RDF storage. Không được che vấn đề bằng Kubernetes replica.

---

## 11. CI and Test Strategy

CI pipeline tối thiểu:

```text
Lint/type check
→ Unit tests
→ Build runtime images
→ Start integration dependencies
→ Run migration
→ Load ontology/test dataset
→ SHACL/SPARQL/rule regression tests
→ Application integration tests
→ Validate Compose production config
→ Scan/tag/publish immutable images
```

Testcontainers có thể dùng cho test suite cần lifecycle isolation. Compose được dùng cho system/integration test bao phủ nhiều service.

CI không được phụ thuộc vào reusable developer volume hoặc dữ liệu tồn tại từ lần chạy trước.

---

## 12. Early Production Operations

Một early-production deployment phải có tối thiểu:

- Linux VM được cập nhật bảo mật.
- Reverse proxy và TLS.
- Firewall chỉ mở public endpoint cần thiết.
- Container restart policy.
- Persistent storage đủ dung lượng.
- Health monitoring.
- Off-host backup.
- Backup retention.
- Restore drill cho PostgreSQL, TDB2 và object storage.
- Deployment rollback bằng image version trước.
- Secret không nằm trong Git, image hoặc Compose file được commit.

Single-VM Compose không cung cấp high availability. Đây là trade-off được chấp nhận cho giai đoạn đầu, không phải tuyên bố production topology cuối cùng.

---

## 13. Kubernetes Adoption Triggers

Chỉ đưa Kubernetes/Helm vào roadmap active khi ít nhất một nhu cầu sau xuất hiện:

- Stateless service cần autoscaling độc lập.
- Yêu cầu high availability có SLO cụ thể.
- Nhiều environment/tenant làm Compose deployment khó kiểm soát.
- Rolling deployment và scheduling đã trở thành operational bottleneck.
- Có đội/người chịu trách nhiệm vận hành cluster.

Trước khi chuyển:

1. Application image phải chạy bất biến.
2. Health/readiness check phải hoàn chỉnh.
3. Database migration phải tách khỏi application replica startup.
4. Secret và configuration contract phải ổn định.
5. PostgreSQL/object storage nên được đánh giá cho managed service.
6. Fuseki/TDB2 phải có stateful deployment và recovery design riêng.

Local development vẫn dùng Compose trừ khi có một quyết định mới chứng minh local Kubernetes đem lại giá trị đủ lớn.

---

## 14. Consequences

### Positive

- Setup local nhất quán và ưu tiên công cụ miễn phí.
- Giảm version drift giữa developer, CI và production.
- Cho phép inner loop nhanh mà vẫn có full-container integration path.
- Production sớm đơn giản và chi phí thấp.
- Có đường nâng cấp lên managed service/Kubernetes mà không đổi semantic architecture.

### Trade-offs

- Phải duy trì Dockerfile và Compose configuration như production code.
- Single-VM production có downtime risk và không có HA.
- Docker Desktop có điều kiện license riêng; tổ chức phải kiểm tra eligibility hoặc dùng Docker Engine/Podman phù hợp.
- Compose-compatible engine có thể có khác biệt, nên canonical CI vẫn cần Docker Compose.
- Stateful RDF storage vẫn là điểm cần thiết kế riêng khi scale.

---

## 15. References

- Docker Docs — Use Compose in production: <https://docs.docker.com/compose/how-tos/production/>
- Docker Docs — Compose Watch: <https://docs.docker.com/compose/how-tos/file-watch/>
- Docker Docs — Docker Desktop license: <https://docs.docker.com/subscription/desktop-license/>
- Apache Jena — Fuseki Docker tools: <https://jena.apache.org/documentation/fuseki2/fuseki-docker.html>
- Apache Jena — TDB2 administration: <https://jena.apache.org/documentation/tdb2/tdb2_admin.html>
- Podman Docs — `podman compose`: <https://docs.podman.io/en/latest/markdown/podman-compose.1.html>
