# Sprint 6 Plan — Retrieval and Coordination

## Sprint Goal

Hoàn thành M4 bằng một vertical slice chạy thật: nhận câu hỏi trong project về
requirement hiện tại và lịch sử, blocker hoặc delivery risk; ánh xạ câu hỏi vào
query template được allowlist; lấy asserted/inferred facts cùng provenance từ
Semantic Core; và trả structured answer có evidence, knowledge status và rule
derivation. Retrieval, projection và LLM chỉ hỗ trợ tìm hoặc diễn đạt context,
không trở thành source of truth và không được vượt project scope.

## Carried Decisions from Sprints 1–5

- Ontology v0.4.0 và canonical 119-check suite là released regression baseline.
  Mọi vocabulary, shape hoặc inference rule mới phải đi qua
  `$projecta-evolve-ontology` và human approval trước khi dependent
  implementation bắt đầu.
- FastAPI là application/orchestration boundary; Java/Javalin Semantic Core là
  nơi duy nhất route RDF graphs, chạy service-authored SPARQL, materialize
  inference và kiểm tra semantic scope. API và LLM không gửi arbitrary SPARQL.
- Asserted facts, inferred facts, candidates, sources và provenance tiếp tục ở
  graph riêng. Mỗi answer phải chỉ rõ knowledge status; inferred fact phải ghi
  rule identifier/version và derivation tới asserted inputs.
- Trusted project/actor context là deployment contract. Named graph routing là
  defense-in-depth, không thay thế authorization; mọi query, citation và entity
  reference phải fail closed khi thiếu hoặc sai project scope.
- RDF/Fuseki là domain source of truth. Retrieval index và projection chỉ là
  rebuildable read models; similarity hoặc LLM output không tạo fact hay
  semantic relation.
- LLM tiếp tục đi qua provider-neutral gateway. Canonical CI dùng deterministic
  replay/fixtures; live provider evaluation là opt-in và không thay thế
  deterministic acceptance evidence.
- Python 3.12, uv, Java 21, Jena 6.1.0 và Compose là build/runtime baseline.
  Không thêm PostgreSQL, vector database, search cluster, broker hoặc workflow
  framework nếu bounded M4 slice chưa chứng minh nhu cầu.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S6-01 — Fix the executable M4 boundary:** Viết use case từ một câu hỏi
  project-scoped tới grounded answer, gồm supported intents, input/output,
  knowledge-status behavior, failure behavior, latency assumptions và một
  acceptance scenario cho requirement history hoặc blocker.
- [x] **S6-02 — Define the retrieval error taxonomy:** Chốt unknown intent,
  unsupported filter, invalid entity, ambiguous match, no evidence, stale
  projection, rule failure, malformed provider output, timeout, unavailable
  dependency và cross-project access.
- [x] **S6-03 — Define M4 competency questions:** Chốt câu hỏi cho current
  requirements, supersession history, unresolved blockers, delivery risk,
  impact review, evidence/source traversal, knowledge status và rule derivation.
- [x] **S6-04 — Audit the released semantic contract:** Dùng
  `$projecta-evolve-ontology` để map từng competency question, answer field và
  rule input/output vào ontology v0.4.0, named graphs, SHACL và query hiện có;
  xuất reuse/gap matrix mà chưa sửa ontology.
- [x] **S6-05 — Resolve required semantic gaps:** Nếu S6-04 có gap, tạo governed
  ontology/rule proposal, fixtures, shapes, competency queries,
  compatibility/migration analysis và review packet; nếu không có gap, ghi bằng
  chứng reuse.
- [x] **S6-06 — Review the M4 semantic boundary:** Human duyệt use case,
  competency questions, answer semantics, rule set, allowed filters và proposal
  ontology trước khi dependent implementation bắt đầu.
- [x] **S6-07 — Benchmark the retrieval baseline:** So sánh service-authored
  SPARQL với full-text/vector options trên dataset M4 theo recall, latency,
  project isolation, rebuild cost và operational complexity; không thêm hạ tầng
  trong task này.
- [x] **S6-08 — Record the retrieval technology decision:** Human chọn bounded
  M4 retrieval path và dùng `$log-decision` nếu lựa chọn thêm storage/index,
  dependency hoặc contract kiến trúc mới; mặc định giữ Fuseki-only khi chưa có
  bằng chứng cần external index.
- [x] **S6-09 — Define the versioned query contract:** Chốt query IDs,
  allowlisted parameters, pagination/limits, stable ordering, result schema,
  version negotiation và response metadata; forbid arbitrary SPARQL, graph IRI
  và tenant/project override.
- [x] **S6-10 — Define the grounded answer contract:** Chốt answer text,
  structured facts, citations, knowledge status, as-of time, rule derivations,
  unanswered/ambiguous state và completeness warnings; citations dùng opaque
  IDs thay vì raw storage paths.
- [x] **S6-11 — Create the versioned M4 evaluation dataset:** Thêm synthetic
  project fixtures cho current/superseded requirements, open/resolved questions,
  blocked tasks, impact changes, asserted/inferred facts, missing evidence,
  ambiguity và cross-project negatives.
- [x] **S6-12 — Define retrieval and grounding thresholds:** Chốt intent/query
  accuracy, fact recall/precision, citation validity, knowledge-status accuracy,
  abstention, cross-project rejection, latency và answer faithfulness; human
  duyệt thresholds trước khi tuning.
- [x] **S6-13 — Implement the Semantic Core query-template registry:** Load only
  versioned service-authored templates, bind typed parameters, enforce bounded
  result limits và reject unknown query IDs or parameters before Fuseki access.
- [x] **S6-14 — Implement current-requirement retrieval:** Trả current asserted
  requirements trong project với stable order, status, effective time và
  provenance references theo S6-09.
- [x] **S6-15 — Implement requirement-history retrieval:** Trả supersession and
  validity chain without overwriting history, including evidence and actor/time
  provenance for every transition.
- [x] **S6-16 — Implement unresolved-blocker retrieval:** Trả open questions và
  dependencies đang block task trong project, kèm supporting asserted facts và
  explicit empty-result behavior.
- [x] **S6-17 — Implement evidence and source traversal:** Resolve each returned
  fact to bounded source metadata/evidence spans and confirmation provenance;
  never expose another project or unrestricted raw payload.
- [x] **S6-18 — Implement the versioned inference runner:** Execute only approved
  rules against asserted project data, replace the project inferred graph
  atomically, and fail without changing the prior inferred snapshot.
- [x] **S6-19 — Implement unresolved-dependency inference:** Materialize the
  approved open-question-blocks-task outcome with rule ID/version and complete
  derivation provenance.
- [x] **S6-20 — Implement delivery-risk inference:** Materialize the approved
  blocked-task-implements-requirement outcome with rule ID/version and complete
  derivation provenance.
- [x] **S6-21 — Implement impact-review inference:** Materialize the approved
  superseded-requirement-affects-task outcome with rule ID/version and complete
  derivation provenance.
- [x] **S6-22 — Implement inference rebuild and replay:** Rebuild inferred state
  deterministically from asserted graphs, prove idempotency, and remove obsolete
  derivations without mutating asserted facts or provenance history.
- [x] **S6-23 — Implement the project-context projection:** Map query rows into a
  typed, versioned read model for requirements, blockers, risks, evidence and
  derivations; keep the projection rebuildable and non-authoritative.
- [x] **S6-24 — Implement projection freshness metadata:** Emit projection
  version, source revision/as-of time and partial/stale indicators so callers do
  not present outdated context as current truth.
- [x] **S6-25 — Implement bounded question interpretation:** Map supported
  natural-language questions to allowlisted query IDs and typed parameters via
  deterministic rules or the provider-neutral gateway; reject invented IDs,
  filters, entity references and cross-project context.
- [x] **S6-26 — Implement grounded answer rendering:** Render only the verified
  project-context projection into the S6-10 contract, preserve citations and
  knowledge status, and abstain when evidence is insufficient or conflicting.
- [x] **S6-27 — Implement answer verification:** Reconcile every rendered claim
  and citation against the retrieved projection, reject unsupported claims, and
  prevent provider text from changing fact, status, source or derivation fields.
- [x] **S6-28 — Implement the M4 API orchestration:** FastAPI accepts the trusted
  question context, interprets the bounded intent, calls Semantic Core,
  verifies/renders the answer and maps S6-02 failures without mutating semantic
  state.
- [x] **S6-29 — Add safe query telemetry:** Record query/answer contract
  versions, query ID, latency, result/citation counts, knowledge-status mix,
  abstention and error class with correlation ID; redact question/source text,
  credentials and provider payload by default.
- [x] **S6-30 — Add Semantic Core unit and contract tests:** Test registry
  allowlists, typed binding, ordering/limits, temporal chains, evidence
  traversal, rule derivation, atomic rebuild and invalid/cross-project requests.
- [x] **S6-31 — Add Fuseki integration tests:** On clean ephemeral data, test all
  M4 templates and three approved rules across asserted/inferred/provenance
  graphs, including idempotent rebuild, stale derivation removal and rollback.
- [x] **S6-32 — Add Python unit and contract tests:** Test intent mapping,
  projection schemas, grounded rendering, citation verification, abstention,
  error mapping, telemetry redaction and no semantic mutation on failure.
- [x] **S6-33 — Build the offline M4 evaluation runner:** Run the versioned
  dataset through deterministic interpretation/retrieval/rendering, report
  metrics by intent and fail when approved retrieval or grounding thresholds
  are missed.
- [x] **S6-34 — Add an opt-in live answer evaluation:** Run the same dataset with
  the approved provider when configured, store a sanitized report and keep
  network/model variance outside canonical CI.
- [x] **S6-35 — Add end-to-end M4 system tests:** Qua HTTP thật, chứng minh
  question → allowlisted query → asserted/inferred retrieval → grounded answer
  cho requirement history và blockers, cùng ambiguity, no-evidence, rule rebuild,
  provider failure và cross-project negatives.
- [x] **S6-36 — Build the canonical Sprint 6 test entry point:** Một Compose
  command chạy ontology/rule regression, Java, Python, offline evaluation và M4
  E2E từ clean ephemeral state rồi cleanup, không cần provider credential.
- [x] **S6-37 — Run compatibility and image validation:** Chạy Sprint 1–5
  regressions, canonical ontology checks, inference rebuild, lint/type/tests,
  Compose config, runtime-image smoke tests và `git diff --check`.
- [x] **S6-38 — Prepare the Sprint 6 review packet:** Tổng hợp contracts,
  ontology/rule decision, benchmark, query registry, dataset/metric reports,
  graph/projection evidence, exact commands và unresolved risks.
- [x] **S6-39 — Approve or revise M4:** Human review semantic meaning, rule
  behavior, retrieval/grounding thresholds và E2E evidence; chỉ đánh dấu M4 hoàn
  thành hoặc release ontology/rule change sau khi mọi governance gate đạt.

## Definition of Done

- API trả lời tối thiểu current requirement, requirement history và unresolved
  blocker questions trong đúng project bằng versioned allowlisted query
  templates; arbitrary SPARQL, graph IRI và cross-project reference bị reject.
- Mỗi answer phân biệt asserted/inferred status, có as-of/freshness metadata và
  citation truy ngược được tới evidence/source cùng confirmation provenance.
- Ba rule outcomes được human approve, materialize riêng trong inferred graph,
  ghi rule ID/version và derivation, rebuild deterministic/idempotent và không
  mutate asserted graph.
- Structured projection có version, stable ordering, bounded results và có thể
  rebuild từ RDF; xóa projection/index không làm mất domain truth.
- Bounded question interpretation không thể tạo query ID, parameter, entity
  reference hoặc scope ngoài allowlist; ambiguity/no-evidence dẫn tới explicit
  abstention hoặc incomplete answer.
- Answer verification phát hiện unsupported claim/citation trước response; LLM
  chỉ diễn đạt verified context và không quyết định truth, authorization,
  knowledge status hoặc rule result.
- Versioned dataset và offline runner tái tạo metrics trong canonical CI; live
  provider evaluation, nếu chạy, chỉ là quality evidence bổ sung.
- Sprint 1–5 regressions, ontology/rule checks, Java/Python suites và clean
  Compose M4 E2E pass; review packet đủ evidence để human quyết định M4.

## Non-Goals and Guardrails

- Không general-purpose enterprise search, arbitrary SPARQL endpoint, raw graph
  browser, unrestricted document Q&A hoặc retrieval ngoài project/workflow.
- Không coi keyword/vector similarity, projection, cache hoặc LLM response là
  fact; không auto-assert candidate và không cho answer tạo semantic mutation.
- Không frontend/dashboard, connector mới, external task synchronization,
  notification, meeting brief, outbound action hoặc autonomous agent workflow.
- Không authentication provider, RBAC/ABAC administration hoặc tenant management;
  sprint vẫn dùng trusted deployment context và test project isolation.
- Không thêm OpenSearch, pgvector, PostgreSQL, Redis, broker hoặc workflow engine
  nếu S6-07/S6-08 chưa chứng minh và phê duyệt nhu cầu cho vertical slice.
- Không production deployment, public ontology release, shared-dataset migration
  hoặc backup/restore program; các phần operational hardening thuộc Sprint 7+.
- Không cho model sinh ontology term, inference rule, SPARQL, graph route,
  citation, knowledge status, policy hoặc authorization decision.

## Expected Artifacts

```text
apps/api/src/projecta_api/retrieval/
docs/architecture/semantic-retrieval.md
docs/architecture/retrieval-benchmark.md
docs/ontology/m4-retrieval-reuse-gap.md
docs/sprint-plans/sprint-6/review-packet.md
docs/use-cases/project-context-question.md
evaluation/sprint-6/
ontology/
services/semantic-core/
scripts/
compose.yaml
```

## Notes / Blockers

- S6-06 là semantic/design gate. S6-09 và S6-13–S6-24 phải chờ exact ontology,
  rule và answer semantics được human approve nếu S6-05 đề xuất thay đổi.
- S6-08 là technology gate. Không thêm external retrieval/index dependency hoặc
  lockfile change trước khi benchmark và decision được duyệt.
- S6-12 là quality gate. Thresholds phải được chốt trước khi tuning intent prompt,
  retrieval weights hoặc answer renderer để tránh điều chỉnh acceptance criteria
  theo kết quả.
- Rule execution chỉ đọc asserted graph và chỉ ghi inferred/provenance graph.
  Candidate, retrieval similarity hoặc model output không được làm rule premise.
- Empty result, unknown và inaccessible là ba trạng thái khác nhau; API không
  được biến access denial thành data absence hoặc tiết lộ entity tồn tại ở project
  khác.
- Canonical CI dùng deterministic fixtures/replay và clean ephemeral volumes.
  S6-34 opt-in vì network, quota, model drift và credential không reproducible.

## Closure

Sprint 6 was closed on 2026-08-04 after explicit user authorization and a
complete canonical acceptance run. The delivered slice includes content-based
source revisions, governed inference snapshot metadata, deterministic rebuilds,
explicit no-evidence abstention, collision-safe opaque identifiers, and failure
telemetry.

Final evidence: ontology 140/140; API 56 passed and 3 environment-gated skips
locally; Semantic Core 39 tests with 7 environment-gated skips locally and
39/39 against Compose Fuseki; Compose API 59 passed; Ruff, strict Pyright,
Spotless, Compose configuration, offline evaluation 6/6, and diff checks passed.
Live-provider evaluation remains opt-in and was not part of the canonical gate.
