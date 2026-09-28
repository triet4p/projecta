# Project Overview

## 1. Tên tạm thời

**Projecta**

Một nền tảng trí tuệ dự án dựa trên ontology, giúp BrSE hợp nhất thông tin từ nhiều kênh giao tiếp và công cụ làm việc, duy trì project memory có cấu trúc, chuẩn bị công việc, research, quản lý requirement, theo dõi task và hỗ trợ điều phối dự án.

Tên sản phẩm có thể thay đổi về sau. Tài liệu này sử dụng tên **Project Intelligence Platform** để nhấn mạnh rằng hệ thống không phải là một chatbot dành riêng cho Microsoft Teams.

---

## 2. Bài toán

BrSE thường đồng thời tham gia nhiều dự án và nhiều cuộc họp trong một ngày. Công việc của họ không chỉ là phiên dịch giữa khách hàng và đội phát triển, mà còn bao gồm:

- Theo dõi requirement và các thay đổi của requirement.
- Ghi nhớ quyết định, câu hỏi mở, giả định và rủi ro.
- Hỏi Dev/Engineer về tiến độ, blocker và khả năng đáp ứng.
- Research các chủ đề kỹ thuật hoặc business liên quan.
- Chuẩn bị nội dung trước cuộc họp.
- Ghi quick note trong cuộc họp.
- Chuyển thông tin thành task, tài liệu, mock hoặc câu hỏi xác nhận.
- Theo dõi nhiều dòng công việc bị chồng chéo giữa các dự án.
- Giao tiếp lại qua Teams, Slack, email hoặc các nền tảng khác.

Thông tin hiện nay thường bị phân tán trong:

- Microsoft Teams, Slack, Zalo hoặc email.
- Quick notes cá nhân.
- Tài liệu dự án.
- Jira, Azure DevOps, Planner hoặc các task system khác.
- Drive, SharePoint, Confluence hoặc kho nội bộ.
- Trí nhớ cá nhân của BrSE.

Các công cụ tóm tắt hoặc chatbot thông thường chỉ tìm và sinh văn bản. Chúng không duy trì được một mô hình nhất quán về:

- Entity nào đang tồn tại trong dự án.
- Requirement nào đã bị thay thế.
- Task nào triển khai requirement nào.
- Question nào đang block task.
- Decision nào được tạo từ note hoặc document nào.
- Fact nào do con người xác nhận, fact nào do AI đề xuất hoặc suy luận.

---

## 3. Tầm nhìn sản phẩm

Xây dựng một **ontology-driven project intelligence platform** có khả năng:

1. Kết nối nhiều nguồn dữ liệu thông qua connector.
2. Chuẩn hóa dữ liệu thành canonical events và source artifacts.
3. Ánh xạ ngôn ngữ tự nhiên vào domain ontology.
4. Duy trì project knowledge graph có provenance.
5. Phân biệt candidate, asserted và inferred knowledge.
6. Hỗ trợ agent truy xuất, lập kế hoạch, research và soạn nội dung.
7. Giữ human-in-the-loop tại các điểm cần trách nhiệm nghiệp vụ.
8. Gửi kết quả và hành động trở lại kênh người dùng đang sử dụng.

Microsoft Teams chỉ là connector đầu tiên. Semantic core không phụ thuộc Teams.

---

## 4. Người dùng mục tiêu

### 4.1. Người dùng chính

- BrSE.
- Project Coordinator.
- Technical Business Analyst.
- Solution Consultant.
- Project Manager làm việc trong môi trường nhiều kênh giao tiếp.

### 4.2. Người dùng liên quan

- Developer và Engineer cập nhật tiến độ.
- Tech Lead xác nhận feasibility và impact.
- Product Owner hoặc Business Analyst xác nhận requirement.
- Manager theo dõi sức khỏe dự án.
- Khách hàng nhận draft, câu hỏi hoặc project update đã được duyệt.

---

## 5. Giá trị cốt lõi

### 5.1. Project continuity

Hệ thống duy trì lịch sử và ý nghĩa của project knowledge, không chỉ lưu các đoạn text rời rạc.

### 5.2. Evidence-grounded intelligence

Mọi fact quan trọng phải có thể truy ngược tới nguồn:

- Note.
- Message.
- Email.
- Document.
- Task system.
- Research source.
- Người xác nhận.
- Rule suy luận.

### 5.3. Cross-project context control

Mọi truy xuất phải có project scope, tenant scope, permission và provenance rõ ràng, tránh trộn dữ liệu giữa các dự án.

### 5.4. Channel independence

Teams, Slack, Zalo, Outlook hoặc Jira được coi là connector. Việc thay đổi hoặc bổ sung connector không yêu cầu viết lại semantic core.

### 5.5. Replaceable LLM

LLM là lớp hiểu ngôn ngữ, đề xuất, lập kế hoạch và diễn đạt. Model có thể được thay thế mà không làm thay đổi ontology, knowledge graph hoặc workflow contracts.

---

## 6. Các năng lực cấp cao

### 6.1. Quick Note và knowledge capture

BrSE có thể ghi nhanh:

- Requirement.
- Decision.
- Question.
- Task.
- Risk.
- Assumption.
- Constraint.
- Progress update.
- Research need.

Một note có thể chứa nhiều nội dung. Người dùng chọn hoặc xác nhận từng
 occurrence/entity và tạo structured capture; server giữ source-version,
 text-anchor và project-scoped identity. AI chỉ được gọi khi người dùng yêu
 cầu để gợi ý một item/type/link/relation cục bộ. Mọi suggestion đều phải qua
 quyết định rõ ràng và append-only receipt trước khi trở thành asserted fact;
 đường manual hoạt động đầy đủ với zero model calls.

### 6.2. Evidence-first assisted authoring

Luồng chính bắt đầu từ task/question hoặc structured note do human tạo:

```text
Human task/question hoặc structured note
→ scoped retrieval/evidence
→ human chọn/xác nhận occurrence/entity
→ server resolve SourceVersion + TextAnchor + opaque identity
→ (tuỳ chọn) AI đề xuất một item/type/link/relation bounded
→ human confirm/edit/reject + append-only receipt
→ approved-only asserted materialization
→ inference và projection
```

Retrieval chỉ là context không authoritative. Relation chỉ được đề xuất sau
khi hai endpoint cùng project đã confirmed, có evidence deterministic và
predicate/direction allowlist. Không có automatic whole-document extraction,
background provider call, model-authored offset/global ID hoặc unreviewed
materialization.

### 6.3. Project memory

Hệ thống trả lời được các câu hỏi như:

- Requirement hiện tại là gì?
- Requirement nào đã bị supersede?
- Task nào đang triển khai requirement này?
- Question nào đang block task?
- Decision này được đưa ra dựa trên tài liệu nào?
- Những thay đổi nào xảy ra kể từ lần cập nhật trước?
- Những fact nào chưa được xác nhận?

### 6.4. Work coordination

- Gợi ý task và assignee.
- Gợi ý dependency và blocker.
- Theo dõi progress claims.
- Phát hiện impact khi requirement thay đổi.
- Chuẩn bị câu hỏi cần hỏi Dev hoặc khách hàng.
- Tổng hợp project health dựa trên fact đã xác nhận và inference rule.

### 6.5. Research support

- Phân rã research question.
- Tìm nguồn.
- Tạo research finding có citation và provenance.
- Liên kết research finding với question, decision, requirement hoặc risk.
- So sánh lựa chọn kỹ thuật theo tiêu chí của dự án.

### 6.6. Meeting preparation

- Lấy task đang mở.
- Lấy question chưa được giải quyết.
- Lấy requirement mới thay đổi.
- Lấy decision gần đây.
- Lấy blocker và risk.
- Tạo meeting brief.

Hệ thống không phụ thuộc transcript. Trong cuộc họp, BrSE có thể mở quick note và ghi thông tin do mình hiểu và chịu trách nhiệm.

### 6.7. Communication assistance

- Soạn Teams/Slack message.
- Soạn email.
- Soạn project update.
- Soạn clarification questions.
- Soạn task description hoặc acceptance criteria.
- Gửi qua connector sau bước policy và approval phù hợp.

---

## 7. Nguyên tắc kiến trúc

### 7.1. Semantic infrastructure first

Ontology, provenance, lifecycle, validation, connector abstraction và policy là core architecture.

### 7.2. Candidate before assertion

Human-authored capture là đường mặc định. LLM hoặc rule chỉ có thể đề xuất
bounded entity/relation/action sau khi có scoped evidence; chỉ semantic core và
quy trình xác nhận mới đưa chúng vào asserted knowledge.

### 7.3. Deterministic where possible

- SHACL kiểm tra dữ liệu.
- Rule engine thực hiện inference xác định.
- RDBMS quản lý workflow state.
- Policy engine kiểm soát quyền.
- LLM chỉ xử lý phần ngôn ngữ hoặc ambiguity.

### 7.4. No transcript dependency

Transcript không phải nguồn dữ liệu cốt lõi. Hệ thống ưu tiên quick note, message, document, task system và nguồn do BrSE chủ động chọn.

### 7.5. Cost-aware optional assistance

Deterministic capture và retrieval chạy trước. Mỗi lần gọi model phải do user
hoặc workflow được phép yêu cầu, giới hạn ở một suggestion bounded, có cache /
dedup theo source-item-revision, budget theo project/user và telemetry về cost
trên accepted assertion. Không gọi model vẫn phải hoàn thành được manual flow.

### 7.6. Core is not MVP

Không thành phần nào sau đây được coi là tùy chọn MVP:

- Domain ontology.
- RDF knowledge graph.
- Candidate/asserted/inferred separation.
- SHACL validation.
- Provenance.
- Connector abstraction.
- Project and tenant scoping.
- Semantic lifecycle.
- Policy-controlled action.
- Operational persistence.

Việc triển khai có thể tăng dần theo connector hoặc quyền truy cập, nhưng kiến trúc lõi phải tồn tại từ đầu.

---

## 8. Định vị sản phẩm

Sản phẩm không phải:

- Meeting transcript summarizer.
- Teams chatbot.
- Vector search trên toàn bộ document.
- LLM wrapper.
- Hệ thống task management thay thế Jira.
- Bot tự động quyết định requirement.

Sản phẩm là:

> Một nền tảng project intelligence dựa trên ontology, giúp BrSE xây dựng và vận hành project memory có cấu trúc, bằng chứng, suy luận và khả năng hành động qua nhiều connector.

---

## 9. Tiêu chí thành công cấp cao

- BrSE truy xuất được project context đáng tin cậy mà không tìm thủ công qua nhiều kênh.
- Hệ thống không trộn dữ liệu giữa project hoặc tenant.
- Mỗi fact quan trọng có provenance.
- Candidate do AI tạo không bị nhầm với fact đã xác nhận.
- Requirement evolution được giữ lại đầy đủ.
- Connector mới được thêm mà không sửa domain ontology cốt lõi.
- LLM có thể thay đổi mà không phải viết lại semantic core.
- Hệ thống giải thích được vì sao một risk, blocker hoặc recommendation được đưa ra.
- Người dùng có thể capture assertion có evidence với zero model calls; AI chỉ
  được coi là copilot đề xuất, không phải nguồn sự thật.
