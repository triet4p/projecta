# Sprint 9 Plan — Provider Runtime Truthfulness

## Sprint Goal

Make every interactive provider operation execute exactly one bounded outbound
request, expose truthful token usage and terminal errors, and keep Assisted
Import usable with the schema its composer can represent.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S9-01 — Codify the nested-retry regression:** Add a test proving every
  production OpenAI SDK client is constructed with retries disabled.
- [x] **S9-02 — Remove implicit provider retries:** Set `max_retries=0` on
  extraction, connection-check, and live-answer clients.
- [x] **S9-03 — Bound extraction generation:** Disable DeepSeek thinking for
  structured extraction and set an explicit output-token ceiling.
- [x] **S9-04 — Enforce an absolute provider deadline:** Cancel an extraction
  after one wall-clock budget even when provider keep-alives continue.
- [x] **S9-05 — Align proxy timeout and error contract:** Give the API enough
  outer budget and return correlated problem JSON for proxy timeouts.
- [x] **S9-06 — Make Assisted Import schema representable:** Do not ask the
  import-only path for relations or links it cannot load into the composer.
- [x] **S9-07 — Preserve reasoning-token evidence:** Capture provider reasoning
  usage separately from final-output usage without logging model content.
- [x] **S9-08 — Run deterministic and live regression:** Pass targeted/full
  tests and verify one real DeepSeek call has one input charge, bounded output,
  valid proposals, and a terminal correlated response.
- [x] **S9-09 — Record the reusable lesson:** Append the SDK nested-retry and
  wall-clock-timeout trap to durable project memory.
- [x] **S9-10 — Preserve server-owned response correlation:** Keep the API's
  canonical response ID on proxied responses while generating an ingress ID
  only for timeout responses authored by Nginx.
- [x] **S9-11 — Project committed source Notes into Graph:** Include bounded
  `Note` and `NoteItem` nodes plus `hasNoteItem` edges from the source graph.
- [x] **S9-12 — Make manual candidates reviewable:** Project label and proposed
  type from their canonical source NoteItem so existing `extracted` candidates
  are visible without rewriting stored RDF.
- [x] **S9-13 — Verify existing-data recovery:** Add query regressions, run the
  full Semantic Core/web gates, reload the service, and prove the current Note
  appears in Graph and its candidates appear in Review Queue.
- [x] **S9-14 — Restore node-detail selection:** Reproduce the correlated
  node-click failure, align detail projection with every released Graph node
  shape, and verify Note, NoteItem, and candidate selections end to end.

## Notes / Blockers

- The 2026-08-10 incident charged exactly three identical 1,507-token inputs:
  OpenAI SDK 2.52.0 defaulted to two retries beneath Projecta's declared
  single-attempt gateway.
- A direct one-call probe completed in 65.106 seconds with 8,094 reasoning
  tokens and only 157 final-output tokens. Interactive extraction does not need
  thinking or an unbounded output budget.
- No ontology vocabulary change is required.
- The corrected live call completed in 1.562 seconds with one provider request,
  1,113 input tokens, 55 output tokens, no reasoning tokens, and exact
  server-derived evidence offsets `28..61`.
- Final validation: API `126 passed, 3 skipped`; full Pyright and Ruff clean;
  Semantic Core `49 passed, 7 skipped`; ontology `140/140`; frontend `15`
  tests plus typecheck/lint/build; API drift, UI contract, implicit-behavior,
  Compose health, Nginx contract/syntax, and whitespace gates passed.
- Existing-data recovery: the committed `Meeting 10/08` source projects as 7
  Graph nodes and 6 edges, while Review Queue exposes all 3 stored candidates
  as `Requirement`, `Task`, and `ResearchFinding`; no RDF rewrite or migration
  was required.
- Node-detail recovery: all 7 existing Graph nodes return HTTP 200 through the
  public API after private Semantic Core transport metadata is removed before
  strict domain validation. API validation is now `127 passed, 3 skipped`.
