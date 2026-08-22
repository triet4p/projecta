# Sprint 12 Human-First Extraction Framework v1

Status: proposal / non-authoritative

Dependency: `S12-RM-53`

Provider calls: `0`

This document does not authorize implementation, provider execution, rerun,
retry, validation, held-out access, Stage B, selection, or promotion. The
section below preserves the complete owner response verbatim as the design
input for the queued Sprint 12 planning tranche.

## Planning interpretation — non-verbatim

The owner response below is preserved verbatim. For Sprint planning, its
constraints are separated as follows.

### Non-negotiable hard guards

- Provider experimentation remains stopped; this document authorizes zero
  calls, reruns, retries, validation, held-out access, Stage B, selection, or
  promotion.
- Every candidate and evidence span is bound to an immutable `SourceVersion`
  and one declared coordinate system; invalid or stale bindings fail closed.
- Only server-resolved, allowlisted, project-scoped entity and relation handles
  may cross the confirmed-entity and materialization boundaries.
- Model drafts remain separated from asserted and inferred graphs; only an
  approved, revision-matched assertion plan may materialize atomically.
- Review receipts, custody, idempotency, provenance, concurrency, independent
  accounting, no-overwrite behavior, and raw-data exclusion are mandatory.
- Human business-quality claims require preregistered correction-burden
  evidence; model metrics alone cannot authorize such a claim.

### Owner-configurable policies

- Source-version granularity, canonicalization policy, and retention periods
  within the immutable source and coordinate contracts.
- Quarantine release, ambiguity escalation, entity confirmation roles, and
  language- or OCR-specific review routing.
- Clause or sentence evidence boundaries, relation allowlists, and explicitly
  governed cross-project exceptions.
- Review queue ordering, UI grouping, correction taxonomy, sampling, telemetry
  retention, and inference rebuild timing.
- Human-study sample size, reviewer roles, languages, manual baseline, and
  correction-burden thresholds.

### Repository-relative implementation references

- [Extraction orchestration](../../../apps/api/src/projecta_api/extraction/service.py)
- [Extraction contracts](../../../apps/api/src/projecta_api/extraction/contracts.py)
- [Candidate ingestion](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/LlmCandidateIngestionService.java)
- [Candidate confirmation](../../../services/semantic-core/src/main/java/org/projecta/semanticcore/CandidateConfirmationService.java)

## Owner response — verbatim

Đúng: thứ cần xây không phải “prompt v10”, mà là một extraction review kernel có state machine, hard guards, provenance và recovery rõ ràng. Mô hình chỉ đề xuất; hệ thống chịu trách nhiệm neo vào nguồn, chặn lỗi và đưa con người vào đúng điểm.

## 1. Kiến trúc mục tiêu

```text
Source
  ↓
Immutable Source Snapshot
  ↓
Deterministic Segmentation + Anchor Index
  ↓
Entity Proposals
  ↓
Span Resolution + Entity Guards
  ├─ QUARANTINED / ABSTAINED
  └─ Human confirms/edits entities
          ↓
Constrained Relation Proposals
          ↓
Endpoint Resolution
          ↓
Deterministic Evidence Selection
          ↓
Grounding + Risk Validation
          ├─ QUARANTINED / ABSTAINED
          └─ Human confirms/edits relations
                  ↓
Approved Assertion Plan
                  ↓
Atomic Materialization
                  ↓
Asserted Graph → Inference → Projection
```

Nguyên tắc trung tâm:

> Model draft không bao giờ được ghi thẳng vào asserted graph. Chỉ một `ApprovedAssertionPlan` đã qua deterministic guards và human approval mới được materialize.

Khung này có thể gắn vào các boundary hiện có: [extraction/service.py](F:/ai-ml/projecta/apps/api/src/projecta_api/extraction/service.py:33), [extraction/contracts.py](F:/ai-ml/projecta/apps/api/src/projecta_api/extraction/contracts.py:46), [LlmCandidateIngestionService.java](F:/ai-ml/projecta/services/semantic-core/src/main/java/org/projecta/semanticcore/LlmCandidateIngestionService.java:12) và [CandidateConfirmationService.java](F:/ai-ml/projecta/services/semantic-core/src/main/java/org/projecta/semanticcore/CandidateConfirmationService.java:14).

## 2. Tách ba state machine độc lập

Không nên có một trạng thái chung kiểu “extraction failed”. Cần tách:

### Source lifecycle

```text
RECEIVED → CANONICALIZED → COMMITTED
                         ↘ SUPERSEDED
```

Mỗi source version chứa:

- `sourceVersionId`
- original và canonical digest
- encoding, newline policy
- coordinate-system version
- immutable canonical text
- normalization map từ original sang canonical

Source bị sửa sẽ tạo version mới. Candidate cũ chuyển thành `STALE`; tuyệt đối không âm thầm remap offset.

### Run lifecycle

```text
CREATED → AUTHORIZED → PROVIDER_ATTEMPTED
                    → RESPONSE_CAPTURED
                    → COMPLETED | PARTIAL | FAILED | QUARANTINED
```

Một provider run thất bại không đồng nghĩa mọi candidate đã tạo đều vô giá trị. Run giữ execution facts; item có lifecycle riêng.

### Candidate lifecycle

```text
PROPOSED
  → CONTRACT_VALID
  → GROUNDED
  → REVIEW_PENDING
  → EDITED
  → APPROVED | REJECTED | ABSTAINED | QUARANTINED | STALE
  → MATERIALIZED
```

Entity và relation có state riêng. Một relation sai evidence không được làm mất entity hợp lệ.

## 3. Source và span kernel

Đây là P0 vì năm lỗi schema của v9 đều là `entity_span_out_of_source`.

Model không nên là authority của offset. Model chỉ trả:

- surface quote;
- entity type;
- context/block ID;
- occurrence nếu quote lặp;
- confidence và abstention reason.

Server thực hiện anchoring:

1. Tìm quote trong đúng source snapshot.
2. Nếu có một occurrence duy nhất, materialize span.
3. Nếu có nhiều occurrence, dùng block/context/occurrence để resolve.
4. Nếu vẫn mơ hồ, chuyển `NEEDS_REVIEW`.
5. Không tìm thấy thì `QUARANTINED`, không tự đoán offset.

`TextAnchor` nên có:

```text
sourceVersionId
start/end
exactQuote
quoteDigest
blockId
occurrence
coordinateSystemVersion
```

Quy ước canonical nên là zero-based, half-open Unicode code-point offsets. Vì JavaScript dùng UTF-16, UI cần mapping do server cung cấp; frontend không được tự diễn giải canonical offsets. Emoji, combining marks, CJK và surrogate pairs phải có property tests riêng.

CRLF/LF cũng phải được coi là một phần của contract:

- product source: digest canonical source version;
- governed Git artifact: hash exact Git blob bằng `git cat-file blob`;
- working-tree digest chỉ là preparation evidence, không thay cho commit custody.

## 4. Entity layer

Entity mention và entity identity phải tách biệt:

```text
MentionCandidate
  ├─ exact source anchor
  ├─ proposed type
  └─ proposed label

EntityLinkCandidate
  ├─ mention candidate
  └─ possible existing project entity
```

Các guard bắt buộc:

- span nằm trong source và exact slice khớp quote;
- type thuộc allowlist;
- local candidate ID chỉ có scope trong một run;
- project entity ID được resolve server-side;
- không merge chỉ vì label giống nhau;
- duplicate/nested/overlapping mentions được giữ độc lập cho tới review;
- coreference chỉ là suggestion, không auto-link.

Human-first flow nên review entity trước. Sau khi người dùng sửa hoặc xác nhận entity, relation model chỉ được nhận danh sách entity ID đã xác nhận. Điều này loại bỏ một lớp lớn lỗi endpoint và hallucination của v9.

## 5. Relation và evidence layer

Relation proposal không được chứa endpoint text tự do:

```text
RelationCandidate {
  predicate
  sourceEntityId
  targetEntityId
  triggerQuote | null
  proposedEvidenceBlockIds[]
  modality
  polarity
  temporalQualifier
}
```

Hard guards:

- predicate thuộc allowlist;
- cả hai endpoint tồn tại trong confirmed entity table;
- hai endpoint khác nhau;
- direction hợp lệ;
- source revision chưa stale;
- evidence xuất phát từ source snapshot;
- predicate yêu cầu trigger thì trigger phải tồn tại;
- evidence phải chứa trigger và các endpoint cần thiết.

Với 20 lỗi evidence của v9, không nên tiếp tục yêu cầu model “viết evidence”. Hệ thống nên:

1. Segment source deterministically thành block/sentence/clause.
2. Model chọn `blockId` hoặc đưa trigger quote.
3. Server tìm clause nhỏ nhất chứa endpoint và trigger.
4. Nếu có đúng một clause hợp lệ, evidence được materialize.
5. Nếu nhiều clause ngang điểm, route sang human review.
6. Nếu không có clause hợp lệ, relation `ABSTAINED` hoặc `QUARANTINED`.

Negation, speculation và conditional phải là metadata first-class:

```text
polarity: positive | negative | unknown
modality: asserted | possible | planned | conditional | unknown
```

Không được biến “Alice may own X” thành assertion `owns(Alice, X)`.

## 6. Risk router human-first

Ban đầu không cần auto-approve. Chỉ cần giảm thao tác cho người dùng:

| Lane | Điều kiện | UX |
|---|---|---|
| Fast review | Tất cả hard guard pass, ít ambiguity | Một phím để approve |
| Focused edit | Grounded nhưng type/predicate/evidence còn mơ hồ | Mở đúng field cần sửa |
| Abstain | Không đủ bằng chứng | Không tạo candidate gây nhiễu |
| Quarantine | Contract/span/custody/security fail | Không hiện như candidate bình thường |
| Stale | Source version đã đổi | Khóa approve, yêu cầu re-extract |

Một entity có thể được approve trong khi relation liên quan vẫn pending. Không nên có “approve all relations” mặc định.

Review UI cần hiển thị đồng thời:

- exact source highlight;
- endpoint và trigger;
- evidence clause;
- finite warning dễ hiểu;
- diff giữa model draft và human edit;
- source/candidate revision;
- keyboard-first interaction.

## 7. Failure disposition

Không phải lỗi nào cũng được retry:

- Transport timeout/rate-limit: retry theo declared budget; interactive nên rất hạn chế.
- Malformed JSON/schema drift: quarantine; không blind retry mặc định.
- Out-of-source/mismatched span: quarantine item.
- Missing trigger/endpoints: giữ entity, quarantine relation.
- Ambiguous repeated mention/coreference: human review.
- Unauthorized project/context: block toàn bộ, sanitized audit.
- Source revision mismatch: stale, không remap.
- Idempotency key cùng key nhưng khác body: fatal conflict.
- Partial run: giữ execution facts, accounting để `unknown` nếu không chứng minh được.
- Prompt injection trong source: coi hoàn toàn là data; extraction runtime không có tool authority.
- Raw payload/privacy leak: custody failure.
- Inference/projection failure: giữ asserted graph, đánh dấu projection stale; không rollback truth đã commit.

Retry phải được tính từ authorization riêng. Authorization được coi là spent tại thời điểm invocation, không phụ thuộc số call thực tế hoàn thành.

## 8. Materialization boundary

Materializer nhận một cấu trúc deterministic:

```text
ApprovedAssertionPlan {
  sourceVersionId
  approvedCandidateRevisions[]
  reviewerDecisionDigests[]
  expectedAssertedGraphRevision
  ontologyVersion
  provenanceActivityId
  idempotencyKey
}
```

Trước commit:

- tất cả candidate ở trạng thái `APPROVED`;
- candidate revision vẫn là revision đã review;
- source chưa stale;
- ontology/predicate/type vẫn hợp lệ;
- SHACL pass;
- idempotency body-match;
- expected graph revision khớp;
- provenance đầy đủ.

Sau đó commit atomically:

```text
asserted graph
+ provenance graph
+ review receipt
+ materialization revision
```

Inference chỉ chạy trên asserted graph. Candidate graph và inferred graph không bao giờ được xem là human-approved truth.

## 9. Telemetry phục vụ “đủ tốt”

Metric chính không nên là F1 đơn thuần mà là correction burden:

- phần trăm note được accept nguyên trạng hoặc chỉ một minor edit;
- median và p90 review time;
- số semantic edits trên mỗi note;
- edit breakdown: span/type/label/predicate/endpoint/evidence;
- abstention usefulness;
- reviewer disagreement;
- assertion reversal sau approval;
- số unsupported assertion được finalized.

Gate đầu tiên hợp lý để preregister:

- ≥70% note: unchanged hoặc một minor edit;
- median review ≤30–45 giây;
- p90 ≤90 giây;
- trung bình ≤1–2 semantic edits/note;
- nhanh hơn manual entry;
- zero unsupported assertion finalized.

F1 vẫn cần để chẩn đoán component, nhưng không được dùng thay correction-burden evaluation.

Telemetry mặc định chỉ lưu IDs, digests, finite reason codes và timings; không lưu raw note hay raw provider payload.

## 10. Accounting và custody

Bài học lớn từ RM50 là không tin aggregate tự khai.

```text
immutable case records
+ provider attempt receipts
+ pricing snapshot
+ usage receipts
        ↓
independent reducer
        ↓
report totals
```

Không chấp nhận report chỉ vì:

```text
report.reconciled == true
```

hoặc vì hai mapping cùng bị mutate vẫn khớp nhau.

Reducer phải derive lại:

- calls/responses;
- valid/invalid items;
- error classes;
- token usage;
- pricing;
- known cost;
- unknown accounting;
- case/run/arm/stage identity.

`unknown` phải giữ là `null/unknown`, không đổi thành 0.

Immutable reports phải atomic-write-once. Test sử dụng temporary output riêng và phải có guard chứng minh v6/v9 không đổi, v8 report vẫn vắng mặt.

## 11. Test framework

Bốn lớp kiểm thử bắt buộc:

1. Property tests

   Unicode, repeated mentions, nested spans, CRLF, chunk base offsets, exact slice, containment.

2. Mutation tests

   Mutate độc lập source revision, span, endpoint, trigger, stage identity, calls, responses, pricing, usage, cost, schema/error counts. Mọi mutation phải bị bắt.

3. Adversarial/default-path tests

   Prompt injection, malicious IRI/labels, unauthorized IDs, OCR noise, multilingual text, long documents, stream cancellation, absent output, existing immutable path và schema drift.

4. Replay/integration tests

   Same source + same config + same idempotency key cho cùng kết quả; body khác phải conflict. Không monkeypatch default paths khi mục tiêu là kiểm chứng live defaults.

Cuối cùng mới là human correction study. Provider experimentation hiện đang đóng, nên toàn bộ kernel, property/mutation/replay tests có thể phát triển offline trước.

## 12. Lộ trình triển khai

- Phase 0: đóng RM53 custody mismatch, chuẩn hóa exact Git-blob hashing và immutable test harness.
- Phase 1: `SourceVersion`, anchoring service, coordinate-system và stale detection.
- Phase 2: per-item entity validation/quarantine; confirmed-entity gate.
- Phase 3: constrained relation extraction và deterministic evidence materializer.
- Phase 4: review decision receipts, optimistic concurrency, risk-routing UI.
- Phase 5: approved-only assertion materializer và inference invalidation.
- Phase 6: correction telemetry và preregistered human-first evaluation.

Graphify cho thấy Projecta đã có phần lớn boundary cần thiết—gateway, normalization, candidate/asserted/provenance graphs, confirmation/rejection và revision-aware projections. Việc cần làm là thêm source-version/evidence kernel và biến flow hiện tại thành workflow item-level có custody chặt, thay vì thay toàn bộ hệ thống.

Đây mới là thiết kế đề xuất, chưa thay đổi code hay Sprint state. Provider experimentation vẫn đóng và RM53 custody closure vẫn cần hoàn tất trước khi bắt đầu implementation.
