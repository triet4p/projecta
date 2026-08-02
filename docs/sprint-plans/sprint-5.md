# Sprint 5 Plan — LLM Extraction and Evaluation

## Sprint Goal

Hoàn thành M3 bằng một vertical slice chạy thật: nhận Quick Note chưa gắn type,
gọi LLM qua gateway độc lập provider để đề xuất typed entity/relation candidates
với exact evidence, confidence và entity links theo project, validate rồi ghi
chúng vào lifecycle hiện có để human review. Chất lượng được đo bằng evaluation
dataset có version; LLM không được tự assertion fact hoặc mở rộng ontology.

## Carried Decisions from Sprints 1–4

- Ontology v0.3.0 và canonical 103-check suite là released regression baseline.
  Mọi vocabulary, shape hoặc semantic rule mới phải đi qua
  `$projecta-evolve-ontology` và human approval trước khi implementation phụ
  thuộc vào thay đổi đó.
- FastAPI là application/orchestration boundary; Java/Javalin Semantic Core là
  nơi duy nhất route và mutate RDF graphs. LLM gateway không truy cập Fuseki.
- Candidate, asserted, inferred, source và provenance graphs tiếp tục tách biệt.
  Model output chỉ là untrusted proposal; SHACL và human review vẫn bắt buộc.
- Evidence offsets dùng Unicode code points và phải trỏ chính xác vào immutable
  source text. Model-provided text, IDs, classes, predicates và links không được
  tin cậy trước normalization và allowlist validation.
- LLM và provider phải thay thế được mà không đổi ontology, knowledge graph,
  extraction schema hoặc workflow contract. Domain code không import provider
  SDK trực tiếp.
- Trusted project/actor context vẫn là deployment contract. Authentication,
  authorization provider và cross-project linking không thuộc sprint.
- Python 3.12, uv lock, Java 21, Jena 6.1.0 và Compose là build/runtime baseline.
  Không thêm workflow framework, vector database hoặc observability platform
  nếu vertical slice chưa chứng minh nhu cầu.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S5-01 — Fix the executable M3 boundary:** Viết use case từ untyped Quick
  Note tới candidate review, gồm input/output, graph diff, failure behavior,
  idempotency boundary, latency/cost assumptions và một acceptance scenario.
- [x] **S5-02 — Define the extraction error taxonomy:** Chốt các lỗi schema,
  unsupported type/relation, invalid evidence, hallucinated link, cross-project
  link, abstention, timeout, rate limit và provider failure.
- [x] **S5-03 — Define M3 competency questions:** Chốt câu hỏi truy ngược source,
  model/prompt version, evidence, confidence, proposed entity/relation, entity
  link, review result và project scope.
- [x] **S5-04 — Audit the released semantic contract:** Dùng
  `$projecta-evolve-ontology` để map từng field và competency question vào term,
  shape và query v0.3.0; xuất reuse/gap matrix mà chưa sửa ontology.
- [x] **S5-05 — Resolve required semantic gaps:** Nếu S5-04 có gap, tạo governed
  ontology proposal, fixtures, SHACL, queries, compatibility/migration analysis
  và review packet; nếu không có gap, ghi bằng chứng không cần ontology change.
- [x] **S5-06 — Review the M3 semantic boundary:** Human duyệt use case, error
  taxonomy, competency questions, allowed classes/predicates, link semantics và
  proposal ontology trước khi dependent implementation bắt đầu.
- [x] **S5-07 — Benchmark the first model-provider adapter:** So sánh các lựa
  chọn khả dụng theo structured output, data handling, cost, latency, local/CI
  testability và SDK isolation; không đặt provider vào domain contract.
- [x] **S5-08 — Record the provider decision:** Human chọn provider đầu tiên và
  dùng `$log-decision` để ghi adapter, model configuration, credential boundary
  và điều kiện thay thế trước khi thêm dependency.
- [x] **S5-09 — Define the versioned extraction contract:** Chốt Pydantic/JSON
  Schema cho entity candidates, relation candidates, evidence spans,
  confidence, abstention và entity-link proposals; forbid arbitrary RDF/IRI.
- [x] **S5-10 — Define the prompt package:** Tạo system instructions, ontology
  allowlist, examples và stable prompt version; coi note và retrieved labels là
  untrusted data, không phải instructions.
- [x] **S5-11 — Create the versioned evaluation dataset:** Thêm representative
  Quick Notes và gold annotations cho supported types, relations, links,
  Unicode spans, ambiguity, empty result và adversarial instructions; không có
  production hoặc sensitive data.
- [x] **S5-12 — Define evaluation metrics and release thresholds:** Chốt schema
  validity, type/relation precision-recall-F1, exact-span score, link accuracy,
  abstention, calibration, latency và cost reporting; human duyệt thresholds
  trước khi tuning prompt/model.
- [x] **S5-13 — Implement the provider-neutral LLM gateway:** Tạo typed request,
  structured response, usage metadata và normalized error interface; domain
  extraction chỉ phụ thuộc interface này.
- [x] **S5-14 — Implement the deterministic replay adapter:** Đọc versioned
  fixtures để unit, integration và CI chạy không cần network, credential hoặc
  nondeterministic model output.
- [x] **S5-15 — Implement the approved provider adapter:** Map gateway contract
  sang đúng một provider SDK với structured output và usage metadata; không để
  provider response type rò sang domain layer.
- [x] **S5-16 — Implement model configuration and resilience:** Fail closed khi
  thiếu credential/model, giới hạn timeout/retry, phân loại rate limit và không
  log secret hoặc raw sensitive payload.
- [x] **S5-17 — Add the project-scoped entity-link candidate read:** Mở rộng
  allowlisted Semantic Core read contract để trả bounded entity IDs, types và
  labels trong đúng project; không expose arbitrary SPARQL hoặc cross-project
  data.
- [x] **S5-18 — Implement typed entity extraction:** Chuyển structured model
  output thành allowlisted entity candidates và exact Unicode evidence spans;
  invalid item không được tới persistence.
- [x] **S5-19 — Implement entity-link proposal:** Link mentions chỉ tới bounded
  entity set của S5-17, giữ confidence/evidence và abstain khi không đủ bằng
  chứng; model không được tự tạo target ID.
- [x] **S5-20 — Implement relation candidate extraction:** Chỉ nhận approved
  predicates giữa candidate/existing entity hợp lệ trong cùng project, với
  evidence và confidence riêng; unsupported relation fail closed.
- [x] **S5-21 — Implement output normalization and validation:** Canonicalize
  ordering/duplicates, recompute evidence text from source offsets, validate
  IDs/types/relations/links và emit error taxonomy trước mọi graph mutation.
- [x] **S5-22 — Extend atomic candidate ingestion:** Semantic Core ghi rich
  entity/relation/link candidates cùng extraction provenance trong một
  transaction; retry không duplicate và failure không để partial graph writes.
- [x] **S5-23 — Implement the M3 API orchestration:** FastAPI nhận untyped note,
  lấy project-scoped link context, gọi gateway, normalize, persist candidates và
  reuse validation/review/read flows mà không tự mutate semantic state.
- [x] **S5-24 — Add safe extraction telemetry:** Ghi structured event cho
  request/model/prompt/schema versions, latency, token usage, result counts và
  error class với correlation ID; redact note text, credentials và provider
  payload mặc định.
- [x] **S5-25 — Add Python unit and contract tests:** Test schemas, gateway
  adapters, Unicode evidence, allowlists, prompt-injection cases, link scope,
  normalization, timeout/retry/error mapping và no-persistence-on-failure.
- [x] **S5-26 — Add Semantic Core ingestion tests:** Test entity/relation/link
  candidate shapes, provenance, transaction rollback, replay idempotency,
  invalid target and cross-project isolation trên ephemeral Fuseki.
- [x] **S5-27 — Build the offline evaluation runner:** Chạy dataset qua replay
  hoặc saved model outputs, tính deterministic metrics theo slice/type và fail
  khi schema hoặc approved quality threshold không đạt.
- [x] **S5-28 — Add an opt-in live provider evaluation:** Chạy cùng dataset với
  provider đã duyệt khi có credential, lưu report không chứa secret/raw payload
  và không làm canonical CI phụ thuộc network.
- [x] **S5-29 — Add end-to-end M3 system tests:** Qua HTTP thật, chứng minh
  untyped note → extraction → SHACL validation → confirm/reject → current and
  evidence reads, cùng abstention, provider failure và cross-project negatives.
- [x] **S5-30 — Build the canonical Sprint 5 test entry point:** Một Compose
  command chạy ontology, Java, Python, replay evaluation và E2E suites từ clean
  ephemeral state, rồi cleanup mà không cần provider credential.
- [x] **S5-31 — Run compatibility and image validation:** Chạy canonical 119
  ontology checks (v0.1–v0.4), Sprint 3–4 regression, lint/type/tests, Compose config,
  runtime-image smoke tests và `git diff --check`.
- [x] **S5-32A — Fix DeepSeek Responses compatibility and live reliability:**
  Align base URL/model/schema with the official Responses API contract, add
  bounded timeout/retry behavior, and rerun the real configured provider suite.
- [x] **S5-32 — Prepare the Sprint 5 review packet:** Tổng hợp contracts,
  prompt/schema/dataset versions, provider decision, metric reports, graph
  before/after, isolation/rollback evidence, exact commands và unresolved risks.
- [x] **S5-33 — Approve or revise M3:** Human review kết quả evaluation và
  end-to-end evidence; chỉ đánh dấu M3 hoàn thành và release semantic change khi
  thresholds, regression suite và governance gates đều đạt.
- [x] **S5-34 — Close corrective implementation blockers:** Preserve exact
  evidence independently from labels, fix generated Turtle and SPARQL JSON
  replay parsing, validate gold spans, separate deterministic Compose E2E from
  the live provider, align every bounded entity type route including
  `ProgressClaim`, and pass the clean canonical suite.
- [ ] **S5-35 — Rerun the corrected live quality gate:** Run the approved
  provider against corrected `s5.v1`, evaluate all quality thresholds, and
  either release M3 or record an explicit quality acceptance/revision decision.

## Definition of Done

- Một untyped Quick Note tạo zero hoặc nhiều typed entity/relation candidates
  hợp lệ với exact source evidence, confidence và project scope; ambiguity có
  thể tạo abstention thay vì hallucination.
- Entity links chỉ tham chiếu bounded entity IDs lấy từ cùng project. Invalid,
  fabricated hoặc cross-project target bị reject trước graph mutation.
- Candidate ghi rõ provider-neutral model ID, model version, prompt version,
  schema/ontology version, extraction activity và source evidence; không model
  output nào trực tiếp xuất hiện trong asserted hoặc inferred graph.
- Semantic persistence atomic và idempotent. Provider/schema/SHACL/storage
  failure không để lại partial source, candidate, link, relation hoặc provenance.
- Domain extraction và tests chạy qua `LLMGateway`; thay replay/provider adapter
  không đổi API, ontology hoặc lifecycle contract.
- Versioned evaluation dataset và runner báo metric theo category, kiểm tra
  approved thresholds và tái tạo được kết quả offline trong canonical CI.
- End-to-end suite chứng minh extraction, validation, human confirm/reject,
  evidence traversal, project isolation và safe failure behavior.
- Sprint 1–4 regressions và canonical ontology checks tiếp tục pass; review
  packet đủ evidence để human quyết định M3.

## Non-Goals and Guardrails

- Không auto-confirm, auto-assert, auto-reject hoặc materialize inference từ
  confidence score; confidence không phải probability of truth.
- Không frontend, bulk extraction, background job orchestration, connector mới,
  note edit/delete, authentication provider, RBAC/ABAC hoặc cross-project link.
- Không hybrid/vector retrieval, general entity resolution trên toàn graph,
  reranking hoặc grounded answer generation; các phần retrieval thuộc Sprint 6.
- Không fine-tune model, tự động optimize prompt trên test set hoặc coi live
  provider output là reproducible CI baseline.
- Không thêm LangGraph, Langfuse, OpenTelemetry backend, PostgreSQL, broker,
  search/vector database hoặc Kubernetes khi chưa có use case vận hành cụ thể.
- Không cho prompt/model tạo ontology term, arbitrary predicate/IRI, SPARQL,
  graph route, external action hoặc policy decision.
- Không deploy production, publish ontology, gửi production data tới provider
  hoặc mutate shared/remote dataset.

## Expected Artifacts

```text
apps/api/src/projecta_api/llm/
apps/api/src/projecta_api/extraction/
docs/architecture/llm-gateway.md
docs/architecture/model-provider-benchmark.md
docs/ontology/llm-extraction-v0.3-reuse-gap.md
docs/sprint-plans/sprint-5/review-packet.md
docs/use-cases/llm-candidate-extraction.md
evaluation/sprint-5/
services/semantic-core/
ontology/
scripts/
compose.yaml
```

## Notes / Blockers

- S5-06 là semantic/design gate. Nếu S5-05 cần ontology change, S5-09 và các
  implementation task phụ thuộc phải chờ exact proposal được human approve.
- S5-08 là technology decision gate. Không thêm provider SDK hoặc lockfile
  dependency trước khi human chọn adapter đầu tiên.
- S5-12 là quality gate. Thresholds phải được chốt trước live tuning để tránh
  điều chỉnh acceptance criteria theo kết quả model.
- Canonical CI dùng replay adapter và offline artifacts. S5-28 là opt-in vì
  network, quota, model drift và credentials không phải điều kiện reproducible.
- Idempotency bảo đảm một semantic outcome cho cùng request; sprint không tuyên
  bố exactly-once model invocation khi retry xảy ra trước persistence.
- Human approval Sprint 4 không tự động approve vocabulary, prompt, provider,
  dataset hoặc quality threshold mới của Sprint 5.
