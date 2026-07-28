# Sprint 2 Plan — Governed Knowledge Lifecycle

## Sprint Goal

Mở rộng ontology v0.1 thành proposal v0.2 cho lifecycle
source → candidate → human review → asserted/inferred, với PROV-O,
temporal history, named-graph isolation và SHACL validation chạy bằng Jena.
Sprint này chỉ tạo semantic contracts, fixtures và executable validation; chưa
triển khai API, UI, LLM extraction, connector hoặc persistent runtime.

## Carried Decisions from Sprint 1

- Giữ nguyên mọi released v0.1 IRI; không rename hoặc tái sử dụng IRI.
- Controlled individuals tiếp tục dùng kebab-case; class dùng PascalCase và
  property dùng camelCase.
- Giữ vocabulary trong `https://w3id.org/projecta/ontology/`. Có thể tách file
  module nhưng không chuyển term sang module namespace nếu chưa có migration
  decision riêng.
- Dùng PROV-O trước khi tạo provenance vocabulary trùng nghĩa.
- Candidate, asserted, inferred, source và provenance phải ở graph riêng.
- Không chọn RDF-star, RDF reification hoặc assertion node trước benchmark Jena
  và human decision.
- Validation entry point duy nhất là
  `docker compose run --build --rm ontology-test`.
- Apache 2.0 tiếp tục áp dụng; w3id.org registration chỉ bắt buộc trước public
  release.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [ ] **S2-01 — Fix the lifecycle slice boundary:** Viết use case từ một
  Sprint 1 `NoteItem` tới candidate, review decision và asserted fact; kèm
  positive example, counterexamples và non-goals.
- [ ] **S2-02 — Draft lifecycle competency questions:** Tạo 12–18 câu hỏi có
  expected answer shape cho knowledge status, evidence, reviewer, current/history
  view, graph isolation, project scope và temporal validity.
- [ ] **S2-03 — Review lifecycle competency questions:** Human duyệt câu hỏi và
  loại các câu đòi API/UI/LLM hoặc domain vocabulary chưa thuộc slice.
- [ ] **S2-04 — Freeze the v0.1 compatibility baseline:** Liệt kê released IRIs,
  graph/query behavior và 32 Sprint 1 checks phải tiếp tục pass; phân loại v0.2
  là additive hay breaking.
- [ ] **S2-05 — Benchmark assertion metadata representations:** Dùng cùng một
  provenance/temporal fixture để so sánh assertion node, RDF reification và
  RDF-star trong Jena về query, SHACL, update và migration impact.
- [ ] **S2-06 — Decide the assertion representation:** Human chọn representation
  hoặc yêu cầu thêm evidence; ghi approved choice bằng `$log-decision`.
- [ ] **S2-07 — Draft the v0.2 term inventory:** Dùng
  `$projecta-evolve-ontology` và semantic commitment interview cho mọi class,
  property, state/value hoặc assertion/activity node được competency questions
  yêu cầu.
- [ ] **S2-08 — Review semantic commitments:** Human duyệt identity, lifecycle,
  class-vs-state-vs-relation, hierarchy, domain/range, provenance, temporal
  semantics và module ownership.
- [ ] **S2-09 — Implement the additive v0.2 vocabulary:** Tạo các Turtle module
  tối thiểu và metadata/version declarations theo approved inventory; không đổi
  v0.1 IRIs.
- [ ] **S2-10 — Define the named-graph contract:** Tạo canonical graph IRI
  templates và dataset fixture cho sources, candidates, asserted, inferred và
  provenance trong một project.
- [ ] **S2-11 — Implement source shapes:** Tạo SHACL cho `Note`/`NoteItem`
  cardinality, datatype, parent relation, project scope và controlled item type;
  kèm conforming và intended-failure fixtures.
- [ ] **S2-12 — Implement candidate evidence shapes:** Validate source evidence,
  proposed ontology version, verification state, generator/model or actor,
  timestamp và project scope; candidate không được masquerade as asserted fact.
- [ ] **S2-13 — Implement isolation shapes:** Phát hiện candidate trong asserted
  graph, inferred fact trong asserted graph, missing project, cross-project
  relation và provenance visibility mismatch.
- [ ] **S2-14 — Implement temporal lifecycle shapes:** Validate permitted
  lifecycle states, reviewer/confirmation evidence, `validFrom`/`validTo`,
  supersession/retraction history và invalid time intervals.
- [ ] **S2-15 — Implement lifecycle competency tests:** Viết SPARQL SELECT/ASK
  với exact expected results cho approved questions, gồm current view và
  historical view mà không overwrite history.
- [ ] **S2-16 — Extend Docker-native validation:** Chạy Jena SHACL positive and
  negative tests, v0.2 query regression và toàn bộ 32 Sprint 1 checks từ
  `ontology-test`; mọi intended-invalid fixture phải fail đúng constraint.
- [ ] **S2-17 — Record inference scope:** Phân tích rule impact; chỉ thêm
  deterministic rule nếu approved competency question cần nó, nếu không ghi rõ
  business inference được defer thay vì tạo rule để minh họa.
- [ ] **S2-18 — Prepare v0.2 compatibility artifacts:** Cập nhật version metadata,
  changelog, compatibility note và migration artifact; migration no-op phải được
  ghi rõ nếu thay đổi hoàn toàn additive.
- [ ] **S2-19 — Run the v0.2 review packet:** Tổng hợp semantic commitments,
  alternatives, artifact diff, validation evidence, compatibility, unresolved
  questions và explicit human actions.
- [ ] **S2-20 — Approve or revise ontology v0.2:** Human quyết định release,
  yêu cầu sửa hoặc giữ `IMPLEMENTED_PENDING_RELEASE_APPROVAL`.

## Definition of Done

- Approved lifecycle competency questions có exact expected results.
- Mọi term mới vượt qua competency gate và semantic commitment gate.
- Assertion metadata representation có benchmark evidence và human decision.
- Không released v0.1 IRI nào bị đổi, xóa hoặc tái sử dụng.
- Jena SHACL pass trên positive fixtures và fail đúng constraint trên từng
  negative fixture.
- Candidate/asserted/inferred/source/provenance graph separation và project
  isolation có automated regression.
- Provenance truy ngược được source, generator/reviewer và lifecycle activity.
- Current và historical temporal queries không phụ thuộc overwrite dữ liệu cũ.
- Toàn bộ 32 Sprint 1 checks tiếp tục pass.
- v0.2 review packet và compatibility/migration artifacts đầy đủ.
- Không có API, UI, LLM, connector, PostgreSQL workflow hoặc production dataset
  mutation trong sprint.

## Non-Goals and Guardrails

- Không triển khai candidate promotion runtime; Semantic Core API thuộc Sprint 3.
- Không xây review UI hoặc automatic extraction.
- Không model retry, cursor, session hay workflow execution state vào ontology.
- Không thêm business inference rule chỉ để demo inferred graph.
- Không đăng ký w3id.org hoặc publish/migrate remote dataset nếu chưa được human
  authorize riêng.
- Note edit/delete và NoteItem dedup chỉ được kéo vào Sprint 2 nếu approved
  competency question chứng minh chúng cần cho lifecycle contract.

## Expected Artifacts

```text
docs/use-cases/knowledge-lifecycle.md
docs/ontology/term-inventory-sprint-2.md
docs/ontology/assertion-representation-benchmark.md
docs/sprint-plans/sprint-2/review-packet.md
ontology/provenance.ttl
ontology/temporal.ttl
ontology/shapes/
ontology/examples/
ontology/competency-questions/
ontology/migrations/
scripts/validate_ontology.py
```
