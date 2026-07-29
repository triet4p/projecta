# Sprint 3 Plan — Executable Semantic Core

## Sprint Goal

Triển khai Semantic Core tối thiểu chạy bằng Java/Kotlin và Apache Jena, thực
thi lifecycle candidate → validate → confirm/reject trên Fuseki/TDB2 theo
ontology v0.2, với domain-safe API, project isolation và transaction tests.
Sprint này hoàn thành M1 nhưng chưa xây Python API, UI, LLM hoặc connector.

## Carried Decisions from Sprints 1–2

- Ontology v0.2, named-graph contract và RDF reification là released contract;
  không đổi semantic term trong sprint nếu chưa qua `$projecta-evolve-ontology`
  và human approval.
- Mọi write vào asserted graph đi qua Semantic Core; client không gửi arbitrary
  SPARQL Update.
- Compose là canonical local/integration workflow. TDB2 chỉ có một owner
  process và persistence nằm ngoài container filesystem.
- Validation regression hiện tại phải tiếp tục chạy bằng
  `docker compose run --build --rm ontology-test` với 73/73 checks.
- Không materialize business inference nếu chưa có approved rule và competency
  question.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S3-01 — Fix the runtime slice boundary:** Viết use case executable cho
  validate, confirm, reject và project-scoped query; nêu precondition,
  postcondition, failure cases, non-goals và expected graph diff.
- [x] **S3-02 — Define the domain-safe API contract:** Chốt request/response,
  error model, idempotency key, project context và HTTP semantics; không expose
  raw SPARQL Update.
- [x] **S3-03 — Review the runtime contract:** Human duyệt lifecycle behavior,
  authorization assumptions, allowed query surface và graph mutation boundary.
- [x] **S3-04 — Benchmark the service baseline:** So sánh Java/Kotlin và
  Spring Boot/Javalin/Quarkus trên Jena integration, startup, image size,
  testing, maintenance và developer workflow.
- [x] **S3-05 — Record the service-stack decision:** Human chọn baseline; ghi
  quyết định bằng `$log-decision` trước khi scaffold service.
- [x] **S3-06 — Scaffold `services/semantic-core`:** Tạo build, module layout,
  pinned dependencies, formatting/linting và unit-test entry point; không thêm
  endpoint ngoài contract.
- [x] **S3-07 — Build the multi-stage image:** Tạo development, test, build và
  non-root runtime targets cạnh service; giữ cùng image lineage cho local và
  production.
- [x] **S3-08 — Add the persistent Fuseki service:** Mở rộng `compose.yaml` với
  health check, internal endpoint, TDB2 volume và ontology bootstrap tách khỏi
  tools-only `jena`; không tạo Compose manifest song song.
- [x] **S3-09 — Wire development and production overrides:** Chỉ publish debug
  ports/hot reload trong `compose.dev.yaml`; dùng immutable image contract,
  restart/resource/logging settings trong `compose.prod.yaml`.
- [x] **S3-10 — Implement configuration and health:** Validate required
  environment variables, readiness against Fuseki và graceful startup/shutdown;
  không chứa secret/default credential trong Git.
- [x] **S3-11 — Implement graph IRI routing:** Tạo typed router từ project ID và
  lifecycle role tới canonical source/candidate/asserted/inferred/provenance
  graph; reject invalid or cross-project targets.
- [x] **S3-12 — Implement candidate loading and validation:** Đọc candidate
  dataset, chạy Jena SHACL bằng released shapes và trả structured violations mà
  chưa mutate asserted/provenance graphs.
- [x] **S3-13 — Implement transactional confirmation:** Trong một write
  transaction, verify candidate, ghi asserted fact và RDF-reified provenance,
  rồi cập nhật review state; rollback toàn bộ khi bất kỳ bước nào fail.
- [x] **S3-14 — Implement transactional rejection:** Ghi review decision và
  provenance nhưng không copy candidate vào asserted graph; retry cùng
  idempotency key không tạo duplicate activity.
- [x] **S3-15 — Implement project-scoped query APIs:** Cung cấp allowlisted
  current/history/evidence queries từ v0.2, bind project server-side và không
  cho query nhìn sang project khác.
- [x] **S3-16 — Add unit and contract tests:** Test graph router, validation
  mapping, API schema, invalid input, idempotency và error translation không cần
  persistent developer volume.
- [x] **S3-17 — Add Fuseki/TDB2 integration tests:** Chứng minh confirm/reject,
  atomic rollback, duplicate retry, concurrent decision conflict, persistence
  across restart và named-graph isolation trên ephemeral dataset.
- [x] **S3-18 — Build the canonical system-test entry point:** Một Compose
  command phải build service, start healthy Fuseki, seed fixtures, run all
  service tests và cleanup; CI không phụ thuộc reusable volume.
- [x] **S3-19 — Run compatibility and Compose validation:** Chạy 73 ontology
  checks, Semantic Core suite, `compose.yaml` + dev/prod config validation,
  runtime image smoke test và `git diff --check`.
- [x] **S3-20 — Prepare the Sprint 3 review packet:** Tổng hợp API examples,
  graph before/after, transaction evidence, image/config evidence, unresolved
  risks và exact commands/results.
- [x] **S3-21 — Approve or revise the executable foundation:** Human approved
  the runtime lifecycle, stack decision, isolation/rollback evidence and M1
  completion on 2026-07-30.

## Definition of Done

- `validate`, `confirm`, `reject` và allowlisted query APIs chạy qua Semantic
  Core trên persistent Fuseki/TDB2.
- Invalid candidate hoặc partial failure không để lại asserted/provenance write.
- Confirm/reject retry idempotent; concurrent conflicting decisions có một kết
  quả xác định và được test.
- Project context được bind server-side; automated tests chứng minh không đọc
  hoặc ghi chéo project.
- Service có multi-stage image, health/readiness và Compose local/production
  configuration hợp lệ.
- Integration suite dùng ephemeral dataset; restart test chứng minh TDB2
  persistence mà không chia sẻ database directory cho nhiều process.
- Toàn bộ 73 ontology checks tiếp tục pass và không released IRI nào thay đổi.
- Review packet đủ evidence để human quyết định hoàn thành M1.

## Non-Goals and Guardrails

- Không xây Python application API, frontend, review UI, LLM extraction,
  connector, PostgreSQL workflow/outbox hoặc authentication provider.
- Không expose general-purpose SPARQL Update; arbitrary read SPARQL chỉ được cân
  nhắc bằng decision riêng.
- Không thêm ontology term, SHACL shape hoặc inference rule chỉ để thuận tiện
  implementation.
- Không thêm Kafka, OpenSearch, Redis, Kubernetes hay full observability stack.
- Không publish ontology, deploy production hoặc mutate remote dataset.

## Expected Artifacts

```text
docs/use-cases/semantic-core-runtime.md
docs/architecture/semantic-core-api.md
docs/architecture/semantic-core-stack-benchmark.md
docs/sprint-plans/sprint-3/review-packet.md
services/semantic-core/
services/semantic-core/Dockerfile
compose.yaml
compose.dev.yaml
compose.prod.yaml
scripts/
```

## Notes / Blockers

- Service language/framework vẫn là decision gate S3-04–S3-05; plan không mặc
  định biến một lựa chọn chưa duyệt thành project truth.
- Authentication chưa thuộc sprint, nhưng API contract phải yêu cầu trusted
  project context để Sprint 4 không phải phá request schema.
- `reason` API chỉ được thêm khi có approved deterministic rule. Với v0.2 hiện
  tại, inferred graph là reserved routing boundary chứ chưa phải deliverable.
- Sprint 3 and M1 were human-approved on 2026-07-30. The approval accepted the
  24-test Fuseki/HTTP system evidence recorded in the review packet.
