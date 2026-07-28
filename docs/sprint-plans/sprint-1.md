# Sprint 1 Plan — Ontology Kernel

## Sprint Goal

Tạo ontology kernel tối thiểu, được human duyệt và chạy kiểm thử bằng Jena cho Quick Note vertical slice đầu tiên, chưa triển khai API, UI, LLM hoặc connector ngoài.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S1-01 — Fix the slice boundary:** Viết use case Quick Note chuẩn, positive example, counterexample và non-goals.
- [x] **S1-02 — Draft competency questions:** Tạo 10–15 câu hỏi có identifier và expected answer shape.
- [x] **S1-03 — Review competency questions:** Human duyệt phạm vi câu hỏi trước khi tạo vocabulary.
- [x] **S1-04 — Propose namespace policy:** Đề xuất base IRI, prefix, naming và ontology-version convention.
- [x] **S1-05 — Record namespace decision:** Sau khi human approve, ghi decision bằng `$log-decision`.
- [x] **S1-06 — Draft the term inventory:** Dùng `$projecta-evolve-ontology` trả lời semantic commitment interview cho từng class/property cần thiết.
- [x] **S1-07 — Review semantic commitments:** Human duyệt meaning, hierarchy, identity, lifecycle và module ownership.
- [x] **S1-08 — Implement core vocabulary:** Tạo các Turtle module tối thiểu cho term đã duyệt; không thêm term “để dành”.
- [x] **S1-09 — Add ontology metadata:** Khai báo imports, version IRI, labels và definitions theo policy đã duyệt.
- [x] **S1-10 — Build the demo graph:** Tạo TriG fixture từ Quick Note use case với project scope và provenance tối thiểu.
- [x] **S1-11 — Implement competency queries:** Viết SPARQL query và expected results cho toàn bộ approved questions.
- [x] **S1-12 — Add the Jena test runner:** Tạo runner tối thiểu để parse ontology/data và chạy competency-query regression.
- [x] **S1-13 — Add negative fixtures:** Dùng SPARQL ASK/data-quality tests chứng minh orphan entity, missing project và invalid relation được phát hiện trong phạm vi Sprint 1.
- [x] **S1-14 — Run the review packet:** Tổng hợp artifact diff, automated evidence, compatibility risks và unresolved questions.
- [x] **S1-14A — Normalize repository layout:** Đưa Compose, Docker/Jena config, scripts, ontology docs và task artifacts về canonical project structure; cập nhật toàn bộ references.
- [x] **S1-15 — Approve or revise ontology v0.1:** Human approved semantic meaning, kebab-case controlled IRIs, Apache 2.0, deferred w3id.org registration, and the repository-local v0.1 release.

## Definition of Done

- 10–15 competency questions được human duyệt và có expected result.
- Mọi class/property mới có semantic commitment answers.
- Turtle/TriG parse thành công bằng Apache Jena.
- Approved SPARQL queries trả đúng kết quả trên demo graph.
- Không còn quyết định mơ hồ về base IRI, naming hoặc module ownership.
- Ontology review packet ghi rõ validation đã chạy và validation chưa có.
- Không có API, UI, LLM hoặc connector code nằm ngoài sprint goal.

## Notes / Blockers

- Sprint 1 chỉ tạo ontology kernel; candidate lifecycle đầy đủ, SHACL và inference materialization thuộc Sprint 2.
- Jena là runtime đã chốt, nhưng Java/Kotlin và service framework có thể hoãn đến Sprint 3 nếu test runner không cần quyết định đó.
- Không dùng RDF-star hoặc reification cho edge metadata trước benchmark/decision riêng.
- Sprint 1 completed on 2026-07-28. Public IRI publication remains deferred
  until w3id.org registration.
