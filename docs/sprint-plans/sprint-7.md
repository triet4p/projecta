# Sprint 7 Plan — Web Experience and User-Managed Runtime Configuration

## Sprint Goal

Hoàn thành M5 bằng một vertical slice chạy thật trong canonical Compose: người
dùng mở React web app, cấu hình LLM mà không sửa `.env`, ghi Quick Note, review
candidate, confirm hoặc reject capability đã được backend hỗ trợ, xem current
knowledge/history/evidence và hỏi các câu M4 có grounded answer. UI chỉ gọi
Application API; credential không đi vào browser persistence, log, telemetry,
RDF hoặc Git; trusted project context vẫn fail closed và không bị biến thành
client-chosen production identity.

## Carried Decisions and Constraints

- Docker Compose tiếp tục là canonical local, CI và early-production topology.
  Web UI là một client/service mới của topology, không thay thế hay nhúng
  FastAPI, Semantic Core hoặc Fuseki vào desktop installer.
- React + TypeScript là frontend baseline. Sprint dùng static SPA phù hợp với
  web deployment và có thể tái sử dụng trong Tauri thin client về sau; không cần
  SSR cho application dashboard này.
- FastAPI là Application API boundary; Java/Javalin Semantic Core vẫn là nơi duy
  nhất route RDF graph, validate/promote candidate và chạy governed semantic
  operations. UI không gọi Fuseki hoặc Semantic Core trực tiếp.
- Trusted project/actor context là deployment-owned. Sprint 7 có thể cung cấp
  một experience adapter bị giới hạn rõ ràng cho local use, nhưng adapter phải
  tắt/fail closed ngoài experience profile và browser không được biết deployment
  secret.
- Interactive LLM profile đi qua runtime-configuration và secret-store ports.
  `PROJECTA_LLM_*` vẫn là provider cho headless, CI và deployment bootstrap,
  nhưng không còn là cách duy nhất để một user cấu hình live extraction.
- Raw credential không được trả lại sau khi ghi, xuất hiện trong frontend state
  lâu dài, browser storage, structured log, telemetry, error detail, RDF,
  fixture hoặc review artifact.
- Sprint không mặc định thay đổi ontology. Nếu capability/UI contract phát hiện
  semantic gap, phải dùng `$projecta-evolve-ontology` và chờ human approval
  trước dependent implementation.
- Candidate confirmation hiện chỉ release Requirement assertion. UI phải biểu
  diễn đúng capability này; không enable transition mà backend chưa hỗ trợ.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S7-01 — Define the executable experience journey:** Viết use case từ mở
  application tới cấu hình LLM, capture/extract note, review candidate và truy
  xuất grounded project context; chốt happy path, recovery path và acceptance
  examples bằng released M2-M4 behavior.
- [x] **S7-02 — Build the backend-to-screen capability matrix:** Map từng endpoint,
  request/response, lifecycle state, error và backend limitation hiện có vào
  screen/action cụ thể; đánh dấu rõ feature nào chưa có API hoặc chỉ hỗ trợ
  Requirement confirmation.
- [x] **S7-03 — Audit API contract gaps for the web slice:** Kiểm tra OpenAPI,
  pagination, stable ordering, redacted errors, idempotency và response fields mà
  UI cần; xuất gap list nhưng chưa mở rộng domain hoặc ontology trong task này.
- [x] **S7-04 — Update the frontend architecture baseline:** Cập nhật tech-stack
  documentation cho React, TypeScript và static SPA build; ghi rõ web là
  canonical client và Tauri chỉ là future thin wrapper.
- [x] **S7-05 — Define the experience-mode context threat model:** Chốt cách local
  web traffic nhận fixed/allowlisted project và actor context mà không trao
  trusted secret cho browser; mô tả production-disable behavior, origin/bind
  restriction và abuse cases.
- [x] **S7-06 — Define the LLM settings security contract:** Chốt metadata nào được
  đọc/ghi, secret write/rotate/delete semantics, redaction, authorization seam,
  audit fields, cache lifetime và fail-closed behavior khi profile thiếu hoặc
  invalid.
- [x] **S7-07 — Review the Sprint 7 architecture and security boundary:** Human
  duyệt experience context, browser/API trust boundary, LLM configuration model,
  secret ownership và explicit non-goals trước implementation phụ thuộc.
- [x] **S7-08 — Publish a versioned frontend-facing API snapshot:** Xuất và commit
  deterministic OpenAPI artifact cho các endpoint Sprint 7; loại internal route,
  trusted secret và provider payload khỏi public client contract.
- [x] **S7-09 — Define the UI problem mapping:** Map finite RFC 7807 codes, field
  errors, retryable/unavailable states và request IDs thành user-facing outcomes
  nhất quán mà không lộ internal detail.
- [x] **S7-10 — Introduce the runtime configuration provider port:** Tách bootstrap
  settings khỏi active LLM profile resolution để application service không đọc
  trực tiếp `.env` tại mọi composition path.
- [x] **S7-11 — Preserve the environment configuration adapter:** Chuyển contract
  `PROJECTA_LLM_*` hiện tại thành adapter fail-closed cho headless, CI, replay và
  deployment bootstrap; giữ compatibility tests cho hai accepted LLM types.
- [x] **S7-12 — Define the persisted LLM profile model:** Chốt provider type, base
  URL, model, secret reference, active state, revision và audit timestamps; không
  đặt raw API key trong model hoặc serialized response.
- [x] **S7-13 — Benchmark the Sprint 7 secret-store baseline:** So sánh application-
  encrypted operational storage, Vault-compatible reference và host OS keyring
  theo Compose compatibility, dynamic writes, backup, rotation, threat model và
  migration path; không thêm dependency trong task này.
- [x] **S7-14 — Approve and record the secret-store choice:** Human đã chọn
  application-encrypted operational storage cho local/self-hosted Sprint 7;
  quyết định được ghi bằng `$log-decision`. S7-15/S7-16 phải giữ
  `SecretStore` provider-neutral và chứng minh master-key custody/recovery.
- [x] **S7-15 — Add the required operational persistence baseline:** Chỉ sau S7-14,
  thêm datastore, schema và migration tối thiểu cần cho LLM profile metadata hoặc
  encrypted secret records; không mở rộng sang connector state ngoài scope.
- [x] **S7-16 — Implement the approved secret-store adapter:** Implement create,
  resolve, rotate và delete theo opaque secret reference; zeroize/limit plaintext
  lifetime trong khả năng runtime và fail closed khi store unavailable.
- [x] **S7-17 — Implement the LLM profile repository:** Persist non-secret profile
  metadata, revision và active selection với optimistic concurrency hoặc
  equivalent conflict protection.
- [x] **S7-18 — Implement the redacted settings read API:** Trả provider metadata,
  active revision và `credentialConfigured`/health status; không bao giờ trả raw
  secret hoặc secret-store locator nội bộ.
- [x] **S7-19 — Implement the settings write API:** Validate allowlisted provider
  type, HTTPS/base URL policy, model và credential input; ghi secret qua
  SecretStore và metadata qua repository như một recoverable workflow.
- [x] **S7-20 — Implement credential rotation and removal:** Cung cấp explicit
  replace/delete operations, idempotent cleanup và clear active profile behavior
  mà không để orphaned secret hoặc plaintext trong response.
- [x] **S7-21 — Implement the provider connection check:** Thực hiện bounded,
  non-domain-mutating connectivity/model check với timeout và sanitized outcome;
  không ghi provider response body hoặc key vào telemetry.
- [x] **S7-22 — Resolve the active gateway at operation time:** Extraction lấy một
  immutable configuration snapshot theo profile revision để settings change có
  hiệu lực không restart và request đang chạy không bị mixed configuration.
- [x] **S7-23 — Add configuration audit telemetry:** Ghi actor/request ID,
  operation, profile revision và outcome cho settings changes/test; cấm key,
  provider payload và sensitive URL components trong event.
- [x] **S7-24 — Implement the local experience context adapter:** Cấp fixed hoặc
  allowlisted local project/actor context qua same-origin server boundary; browser
  không gửi trusted secret và adapter từ chối start khi production profile bật.
- [x] **S7-25 — Scaffold the React and TypeScript SPA:** Tạo một working
  `apps/web` vertical skeleton bằng Vite với route entry, production build và
  không thêm placeholder feature modules ngoài Sprint 7.
- [x] **S7-26 — Configure frontend quality tooling:** Thêm pinned package lock,
  TypeScript strict checking, lint/format và unit-test commands cho `apps/web`.
- [x] **S7-27 — Generate the typed Application API client:** Sinh types/client từ
  S7-08, wrap request IDs, idempotency keys và RFC 7807 parsing, đồng thời thêm
  deterministic drift check.
- [x] **S7-28 — Build the application shell:** Tạo navigation, loading/empty/error
  surfaces, local-experience banner và API/runtime health status mà chưa chứa
  domain workflow logic.
- [x] **S7-29 — Build the LLM settings screen:** Cho phép edit provider/base
  URL/model, set/rotate/delete credential và chạy connection check; UI chỉ nhận
  redacted credential state.
- [x] **S7-30 — Build the Quick Note extraction screen:** Nhập raw note, giữ Unicode
  code-point semantics, submit idempotently và hiển thị extracted entities,
  relations, links, evidence spans hoặc explicit abstention.
- [x] **S7-31 — Build the manual typed capture screen:** Cho phép user chọn ordered,
  non-overlapping typed spans và preview exact evidence trước khi gọi released M2
  capture contract.
- [x] **S7-32 — Build the candidate review screen:** Hiển thị validation result và
  lifecycle state, cho confirm Requirement hoặc reject với reason, ngăn double
  decision và không enable unsupported assertion types.
- [x] **S7-33 — Build the knowledge and evidence view:** Hiển thị current knowledge
  items, candidate history và item evidence/provenance qua opaque IDs; không lộ
  graph IRI, storage URL hoặc arbitrary query control.
- [x] **S7-34 — Build the grounded project Q&A screen:** Gửi bounded M4 questions,
  hiển thị answer completeness, asserted/inferred status, citations, derivation
  và freshness warnings mà không cho user gửi SPARQL.
- [x] **S7-35 — Build the experience diagnostics panel:** Hiển thị liveness,
  dependency availability, sanitized request IDs và experience-only inference
  rebuild control; không biến panel thành production admin console.
- [x] **S7-36 — Add frontend accessibility and keyboard coverage:** Kiểm tra label,
  focus order, error announcement, contrast, keyboard note/review flow và layout
  ở desktop-width lẫn narrow viewport.
- [x] **S7-37 — Containerize and wire the web client:** Thêm multi-stage web image,
  Compose frontend profile, health check và same-origin API routing; production
  build không chứa dev server, source bind mount hoặc trusted secret trong asset.
- [x] **S7-38 — Add backend configuration and secret tests:** Test validation,
  redaction, rotation/delete, unavailable store, concurrent revision, dynamic
  gateway snapshot và preservation của environment adapter.
- [x] **S7-39 — Add frontend unit and component tests:** Test form validation,
  problem mapping, capability gating, evidence offsets, state transitions và
  secret-field clearing bằng mocked generated client.
- [x] **S7-40 — Add the API contract drift gate:** CI regenerate OpenAPI types và
  fail khi committed snapshot/client lệch backend hoặc chứa forbidden internal
  fields.
- [x] **S7-41 — Add browser end-to-end tests:** Dùng một browser runner để cover
  settings, Quick Note extraction/capture, candidate validate/confirm/reject,
  knowledge/evidence và grounded Q&A trên deterministic fixtures.
- [x] **S7-42 — Add clean Compose system acceptance:** Từ clean volumes, build/start
  web, API, Semantic Core và Fuseki, chạy critical browser journey, restart
  services và xác minh profile metadata/secret behavior theo selected store.
- [x] **S7-43 — Add secret-leak regression checks:** Scan browser storage, rendered
  DOM, network responses, structured logs, telemetry, RDF fixtures và built web
  assets để chứng minh test credential không xuất hiện ngoài approved store.
- [x] **S7-44 — Run compatibility and image validation:** Chạy Sprint 1-6 canonical
  suites, Python/Java/frontend checks, production web image build và merged
  Compose config validation; không báo pass cho command chưa được cấu hình.
- [x] **S7-45 — Write the operator and user runbooks:** Tài liệu hóa local startup,
  first-run settings, credential rotation/removal, reset/recovery, supported UI
  capabilities và production-disabled experience behavior.
- [x] **S7-46 — Prepare the Sprint 7 review packet:** Tổng hợp architecture/security
  approvals, API/UI matrix, screenshots, test evidence, secret-leak evidence,
  known limitations và unresolved risks.
- [x] **S7-46A — Align the web extraction timeout budget:** Giữ same-origin API
  proxy mở qua bounded provider retry budget, thêm regression gate và bảo đảm UI
  nhận result hoặc sanitized Application API problem thay vì Nginx 504 ở giây 60.
- [ ] **S7-47 — Approve or revise M5:** Human chạy acceptance journey, review secret
  boundary và UI truthfulness; chỉ mark Sprint 7/M5 complete sau explicit product
  và security acceptance.

## Definition of Done

- Một clean canonical Compose run có thể phục vụ React web app và released
  FastAPI/Semantic Core/Fuseki stack qua documented URL và health checks.
- User cấu hình provider type, base URL, model và credential từ Settings UI mà
  không sửa `.env`; headless/CI environment configuration vẫn pass compatibility.
- Raw credential không xuất hiện trong API read response, browser persistence,
  DOM sau submit, client bundle, log, telemetry, RDF, fixture hoặc review packet;
  rotation/delete và unavailable-store behavior có automated evidence.
- Browser hoàn thành Quick Note extraction hoặc typed capture, validation,
  Requirement confirmation hoặc candidate rejection, rồi xem current knowledge,
  history và evidence trong đúng trusted project.
- Browser hỏi current requirements, requirement history và unresolved blockers;
  answer hiển thị completeness, asserted/inferred status, citations, derivation và
  freshness theo released M4 contract.
- UI không enable unsupported candidate transition, không cho arbitrary SPARQL,
  graph IRI hoặc project/actor override, và không gọi Semantic Core/Fuseki trực
  tiếp.
- Experience context adapter chỉ hoạt động trong explicit local profile, không
  đưa trusted secret vào browser và fail closed khi production mode được chọn.
- Generated API client có deterministic drift gate; frontend unit/component,
  browser E2E, backend settings/secret, clean Compose và Sprint 1-6 regression
  suites pass.
- Review packet đủ evidence để human quyết định M5; không claim production-ready
  connector, authentication hoặc desktop delivery từ kết quả Sprint 7.

## Non-Goals and Guardrails

- Không triển khai Teams, Outlook, Jira hoặc connector production; không webhook,
  polling, OAuth consent, outbound action hay external task synchronization.
- Không triển khai full authentication provider, RBAC/ABAC administration hoặc
  tenant management. Experience context là local-only bridge, không phải auth.
- Không đóng gói Docker, Python, JVM, Fuseki hoặc operational database vào desktop
  app; không tạo Tauri/Electron/.NET client trong sprint này.
- Không cung cấp offline semantic runtime, local-first graph replication, tray,
  global shortcut, native notification hoặc OS keyring adapter.
- Không lưu raw secret trong browser storage, source-controlled config, `.env`,
  general application table, RDF hoặc logs. Deployment bootstrap/master secret
  vẫn phải đi qua Docker secret, environment injection hoặc approved secret
  manager boundary.
- Không mở arbitrary SPARQL, raw graph explorer, storage URL, internal exception,
  provider payload hoặc trusted deployment header cho UI.
- Không mở rộng candidate confirmation ngoài released Requirement contract chỉ để
  làm UI đầy đủ; domain/ontology capability mới phải có sprint và approval riêng.
- Không thêm search cluster, broker, Kubernetes hoặc full observability stack nếu
  Sprint 7 vertical slice không chứng minh nhu cầu.

## Expected Artifacts

```text
apps/web/
apps/web/package-lock.json
docs/architecture/web-experience-api-gap-audit.md
docs/architecture/web-experience-capability-matrix.md
docs/architecture/experience-context-threat-model.md
docs/architecture/runtime-configuration.md
docs/architecture/web-experience-problem-mapping.md
docs/architecture/secret-store-benchmark.md
docs/architecture/application-api.sprint7.openapi.json
apps/api/src/projecta_api/configuration/
docs/architecture/application-api.md
docs/sprint-plans/sprint-7/review-packet.md
docs/use-cases/web-experience.md
docs/sprint-plans/sprint-7/artifacts/task_S7-15_summary.md through task_S7-27_summary.md
docs/sprint-plans/sprint-7/artifacts/task_S7-28_summary.md through task_S7-35_summary.md
docs/sprint-plans/sprint-7/artifacts/task_S7-36_summary.md through task_S7-46A_summary.md
apps/web/Dockerfile
apps/web/nginx.conf
apps/web/playwright.config.ts
apps/web/tests/e2e/sprint7.spec.ts
scripts/run_sprint7_acceptance.ps1
scripts/check_secret_leaks.ps1
scripts/run_sprint7_validation.ps1
docs/runbooks/sprint-7-local-experience.md
docs/runbooks/sprint-7-operations.md
compose.yaml
compose.dev.yaml
compose.prod.yaml
```

Operational persistence is now limited to the approved SQLite metadata/ciphertext
baseline; connector state and production secret-manager migration remain out of
scope.

## Notes / Blockers

- S7-07 là architecture/security gate đã được human approve. S7-08–S7-27 giữ
  đúng trust/configuration contracts; S7-28 trở đi vẫn là công việc frontend
  workflow và acceptance riêng.
- S7-14 đã chọn application-encrypted operational storage làm baseline
  local/self-hosted. S7-15–S7-27 đã hoàn tất với master-key custody,
  persistence, adapter, settings boundary, local context, SPA scaffold và
  typed client evidence; không thêm Vault service hay OS-specific keyring vào
  canonical Compose topology.
- Nếu S7-03 phát hiện thiếu domain endpoint hoặc semantic term, task phụ thuộc phải
  dừng; dùng `$projecta-evolve-ontology` cho semantic gap và lấy human approval.
- Frontend có thể giữ candidate IDs trong memory/session workflow, nhưng reload
  recovery chỉ được hứa khi API có released list/read contract tương ứng.
- Connection check chỉ chứng minh endpoint/model credential có thể dùng; nó không
  thay thế live extraction quality gate của Sprint 5.
- Browser E2E phải dùng deterministic replay hoặc fake provider mặc định. Live
  provider test là opt-in vì network, quota, credential và model drift.
- Production authentication, server secret manager integration và connector
  scopes vẫn là Sprint 8+ work; Sprint 7 chỉ tạo seam và evidence cần để không
  phải viết lại UI/config boundary.
