# Sprint 4 Plan — Manual Quick Note Slice

## Sprint Goal

Hoàn thành M2 bằng một vertical slice chạy thật: FastAPI nhận Quick Note theo
project, Semantic Core ghi source và deterministic candidates có evidence,
human confirm/reject qua lifecycle đã phát hành, rồi API đọc lại asserted item
và provenance. Sprint không dùng LLM, UI hoặc tạo inference rule chưa được
duyệt.

## Carried Decisions from Sprints 1–3

- Ontology v0.2 và 73-check suite là released regression baseline. Mọi semantic
  gap phải đi qua `$projecta-evolve-ontology` và human approval trước khi code
  phụ thuộc vào thay đổi đó.
- Python/FastAPI là application boundary; Java/Javalin Semantic Core là nơi duy
  nhất được route và mutate RDF graphs.
- Deterministic extraction chỉ chuyển các note segment do người dùng gắn type
  thành candidates. Nó không suy đoán type, entity link hoặc sự thật.
- Trusted project/actor context tiếp tục là deployment contract; authentication
  provider và end-user authorization vẫn ngoài sprint.
- Compose là canonical integration workflow. Không thêm PostgreSQL, broker,
  object storage hoặc search nếu slice chưa cần operational state tương ứng.
- Inferred graph vẫn tách biệt nhưng không materialize fact khi chưa có
  competency question và deterministic rule được human duyệt.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S4-01 — Fix the executable Quick Note boundary:** Cập nhật use case với
  request, typed segments, evidence offsets, graph diffs, failure cases,
  idempotency, edit/delete non-goals và end-to-end acceptance scenario.
- [x] **S4-02 — Define M2 competency questions:** Chốt câu hỏi cho note source,
  candidate evidence, review status, asserted result và provenance chain; nêu
  rõ inference output không phải acceptance criterion của sprint.
- [x] **S4-03 — Audit the released semantic contract:** Dùng
  `$projecta-evolve-ontology` để map từng field/CQ vào term, shape và query v0.2;
  xuất reuse/gap matrix, không sửa ontology trong task này.
- [x] **S4-04 — Resolve any semantic gap:** Nếu S4-03 tìm thấy gap bắt buộc, tạo
  một governed ontology proposal đầy đủ và dừng dependent tasks ở human gate;
  nếu không có gap, ghi bằng chứng “no ontology change required”.
- [x] **S4-05 — Review the M2 contract:** Human duyệt boundary, competency
  questions, reuse/gap result, deterministic extraction semantics và việc defer
  inference rule trước khi implementation.
- [x] **S4-06 — Define the application API contract:** Chốt FastAPI endpoints,
  Pydantic schemas, trusted context propagation, error mapping, idempotency và
  response models cho capture, candidate review và current/evidence reads.
- [x] **S4-07 — Extend the Semantic Core contract:** Định nghĩa domain-safe
  source/candidate ingestion operation; client không được gửi graph IRI,
  arbitrary RDF hay SPARQL.
- [x] **S4-08 — Select the Python build baseline:** So sánh `uv` và Poetry theo
  lock reproducibility, container workflow, test/lint tooling và maintenance;
  human chọn và ghi decision trước khi scaffold.
- [x] **S4-09 — Scaffold `apps/api`:** Tạo package, locked dependencies,
  configuration, formatting, linting và unit-test entry point chỉ theo contract
  đã duyệt.
- [x] **S4-10 — Build the FastAPI image:** Tạo multi-stage dev, test và non-root
  runtime targets với cùng dependency lock và health command.
- [x] **S4-11 — Wire Compose topology:** Thêm API vào base/dev/prod overlays,
  health dependency tới Semantic Core, internal networking và environment
  contract; không tạo manifest song song.
- [x] **S4-12 — Implement trusted context and errors:** Parse trusted
  project/actor/request context, reject missing context và map downstream
  problem details mà không lộ Fuseki, graph IRI hoặc stack trace.
- [x] **S4-13 — Implement typed Quick Note capture:** Validate raw note và
  ordered typed segments, preserve exact evidence offsets, normalize canonical
  request và generate stable opaque IDs.
- [x] **S4-14 — Implement atomic source/candidate ingestion:** Semantic Core ghi
  Note/NoteItems vào sources graph, candidates vào candidates graph và
  provenance cần thiết trong một transaction; retry không tạo duplicate.
- [x] **S4-15 — Implement deterministic candidate mapping:** Map allowlisted
  human-selected item types vào released candidate representation; unknown type
  hoặc invalid evidence fail trước mọi graph mutation.
- [x] **S4-16 — Implement review orchestration:** FastAPI gọi validate,
  confirm/reject và preserve Semantic Core `200/201/4xx` idempotency semantics;
  không tự ghi semantic state.
- [x] **S4-17 — Implement M2 read flow:** Trả candidate history, current asserted
  items và evidence chain theo project scope qua allowlisted Semantic Core
  endpoints.
- [x] **S4-18 — Add Python unit and contract tests:** Test schemas, offset
  boundaries, deterministic mapping, context, downstream error translation và
  retry behavior bằng fake Semantic Core client.
- [x] **S4-19 — Add Semantic Core ingestion tests:** Test transaction rollback,
  duplicate capture replay, malformed evidence, cross-project isolation và
  source/candidate graph separation trên ephemeral Fuseki.
- [x] **S4-20 — Add end-to-end M2 system tests:** Qua HTTP thật, chứng minh
  capture → candidates → validate → confirm/reject → current/evidence reads,
  restart persistence và không có inferred fact giả.
- [x] **S4-21 — Build the canonical Sprint 4 test entry point:** Một Compose
  command build images, start healthy dependencies, seed only required context,
  run ontology/Java/Python/E2E suites và cleanup ephemeral state.
- [x] **S4-22 — Run compatibility and image validation:** Chạy 73 ontology
  checks, Sprint 3 regression, Python checks, Compose config validation,
  runtime-image smoke tests và `git diff --check`.
- [x] **S4-23 — Prepare the Sprint 4 review packet:** Tổng hợp API examples,
  before/after graphs, CQ results, transaction/isolation/idempotency evidence,
  image evidence, exact commands và unresolved risks.
- [x] **S4-24R — Close the static-review hardening findings:** Fail closed when
  trusted context is not configured, align Unicode code-point offsets across
  runtimes, validate source/evidence/candidate graphs before capture, preserve
  candidate type at confirmation, use opaque server-derived IDs, record
  validation provenance atomically, complete M2 evidence/status, and map all
  downstream transport failures to the problem contract.
- [x] **S4-24 — Approve or revise M2:** Human approved the validated end-to-end
  Quick Note lifecycle, M2 completion, and ontology v0.3.0 release on
  2026-08-01.

## Definition of Done

- Một typed Quick Note tạo đúng source artifacts và một candidate cho mỗi
  segment hợp lệ, với evidence và project scope đầy đủ.
- Capture retry idempotent; validation hoặc storage failure không để lại partial
  source, candidate hay provenance write.
- Confirmed candidate xuất hiện trong current asserted view; rejected candidate
  không tạo asserted item; cả hai có history/evidence truy ngược được.
- FastAPI không nhận graph IRI/RDF/SPARQL và không truy cập Fuseki trực tiếp.
- Automated tests chứng minh không đọc/ghi chéo project và source, candidate,
  asserted, inferred, provenance không bị trộn.
- Canonical Compose suite chạy từ clean ephemeral state; Sprint 3 và 73 ontology
  checks không regression.
- Review packet đủ bằng chứng để human quyết định M2.

## Non-Goals and Guardrails

- Không có LLM extraction, automatic classification, entity linking hoặc
  confidence score.
- Không có frontend, authentication provider, RBAC/ABAC, connector ngoài
  Manual/Quick Note, note edit/delete hoặc bulk review.
- Không thêm PostgreSQL chỉ để lưu trùng semantic truth; operational database sẽ
  được đưa vào khi workflow/outbox/projection có use case cụ thể.
- Không tạo hay materialize inference rule để thỏa milestone. Rule đầu tiên phải
  có competency question, derivation provenance, negative test và human semantic
  approval riêng.
- Không deploy production, publish ontology hoặc mutate shared dataset.

## Expected Artifacts

```text
apps/api/
apps/api/Dockerfile
docs/architecture/application-api.md
docs/ontology/quick-note-v0.2-reuse-gap.md
docs/sprint-plans/sprint-4/review-packet.md
docs/use-cases/quick-note.md
services/semantic-core/
compose.yaml
compose.dev.yaml
compose.prod.yaml
scripts/
```

## Notes / Blockers

- S4-05 là human design gate. S4-08 chỉ bắt đầu sau gate này.
- Nếu S4-04 cần vocabulary, shape hoặc rule mới, các task phụ thuộc phải chờ
  exact semantic proposal được human duyệt và release theo skill; approval Sprint
  1–3 không áp dụng cho proposal mới.
- M2 được điều chỉnh từ “assertion → inference” thành “assertion + preserved
  inference boundary”. Materialized business inference thuộc milestone có
  competency question thực tế, dự kiến Sprint 6.
