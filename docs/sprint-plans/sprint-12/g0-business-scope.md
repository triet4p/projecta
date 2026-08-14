# Sprint 12 G0 Business Scope Review Packet

**Status:** `APPROVED`

**Sprint:** Sprint 12 — Business Semantic Quality and Evaluation

**Release target:** None. Sprint 12 does not authorize a product release.

**Decision requested:** Approve, revise, or reject the business scope and
evaluation boundary below before dataset-contract work begins.

## 1. G0 decision record

| Field | Value |
| --- | --- |
| Gate | G0 — Business Scope |
| Prepared by | Projecta implementation agent |
| Prepared on | 2026-08-14 |
| Decision | `APPROVED` |
| Approval authority | Project owner |
| Next gate if approved | G1 — Dataset Contract |
| Blocking condition | No dataset authoring at scale or optimization until G0 is approved |

The project owner explicitly approved every G0 checklist item without revision
on 2026-08-14. G1 dataset-contract design is now authorized.

## 2. Released evaluation surface (S12-01)

Sprint 12 evaluates the released v0.6.0 semantic path as a bounded product
workflow, not as an abstract model benchmark.

| Released boundary | What is evaluated | What is not assumed |
| --- | --- | --- |
| Manual structured Quick Note | Typed source capture, ordered evidence, project scope, candidate creation and review continuity | That manually typed notes represent all real project material |
| LLM-assisted untyped Quick Note | Allowlisted entity/relation proposals, exact evidence spans, bounded links, abstention, candidate provenance | That a schema-valid proposal is semantically useful or safe by itself |
| Candidate review | Inspect, edit, confirm and reject outcomes; correction effort and disposition | Automatic assertion or autonomous business decisions |
| Semantic lifecycle | Candidate/asserted/inferred separation, SHACL, provenance, project isolation and fail-explicit behavior | That all business concepts already fit the released ontology |
| Graph projection | Opaque, bounded project graph and knowledge views for review and inspection | Raw RDF, arbitrary graph traversal or browser-owned identifiers |
| Grounded project questions | Supported project-scoped intents, factual answers, citations, completeness, freshness and abstention | General enterprise search or arbitrary SPARQL |
| v0.6.0 GitHub ingestion | Source/evidence/candidate/review continuity from the released public read-only connector | Provider generalization, continuous synchronization or authenticated/private access |
| Existing evaluation harness | Sprint 5 extraction contract and Sprint 6 retrieval replay fixtures as regression baselines | That eight synthetic Sprint 5 cases prove business readiness |

The quality benchmark therefore covers both atomic notes and longitudinal
episodes that pass through capture/extraction, review, graph state and grounded
question checkpoints. Operational and provider boundaries remain hard
invariants, not quality trade-offs.

## 3. Buyer-facing hypothesis (S12-02)

For BrSEs and adjacent project-team roles who turn fragmented project notes into
requirements, decisions, risks, questions and coordination context, Projecta
should reduce the effort required to create and maintain traceable project
knowledge while preserving human review and project isolation.

The hypothesis is supported only if the benchmark shows all of the following:

- semantic proposals are correct enough to be reviewable, not merely schema-valid;
- evidence, provenance, lifecycle and project boundaries remain intact;
- reviewers spend less time structuring equivalent material than with a manual
  baseline, without an unacceptable increase in correction burden;
- grounded project answers are factually correct, cited and appropriately
  incomplete or abstained when the evidence does not support an answer; and
- the result is reproducible for the named dataset, configuration and model
  rather than presented as a universal AI capability claim.

## 4. Priority business journeys (S12-03)

The G0 benchmark contains eight ordered journeys. Each journey must appear in
both atomic cases where applicable and longitudinal scenarios where temporal
state matters.

| Rank | Journey | Business question | Required checkpoints |
| ---: | --- | --- | --- |
| 1 | Capture a structured Quick Note | Can a BrSE record typed project knowledge with evidence and correct type boundaries? | Source, note items, candidate/review state |
| 2 | Extract an untyped Quick Note | Can Projecta turn natural-language material into bounded, evidence-backed proposals? | Extraction, spans, links, abstention, candidate |
| 3 | Review and correct candidates | Can a reviewer accept, make a minor/major correction, or reject without losing provenance? | Candidate, review decision, asserted outcome |
| 4 | Manage requirement and decision change | Can the system preserve supersession, contradiction and temporal history instead of overwriting it? | Ordered events, graph checkpoints, evidence chain |
| 5 | Distinguish requests, commitments, risks and blockers | Can the system avoid turning discussion or speculation into authoritative work state? | Type/abstention, review disposition, project question |
| 6 | Answer grounded project questions | Can a user retrieve current and historical knowledge with correct citations and appropriate abstention? | Retrieval intent, facts, citations, freshness/completeness |
| 7 | Handle ambiguity, hostile text and isolation boundaries | Can the system reject unsupported claims, prompt injection, fabricated links and cross-project references safely? | Hard invariants, error response, no mutation |
| 8 | Maintain a longitudinal project episode | Can the complete workflow preserve useful knowledge across updates, duplicates, contradictions and review decisions? | Timeline, source/candidate/asserted/inferred checkpoints, blinded review |

The journey set intentionally prioritizes the released value chain and defers
outbound action, continuous synchronization, broad tenant administration and
new connectors.

## 5. Target roles and responsibilities (S12-04)

| Role | Primary responsibility in benchmark | Must not be treated as |
| --- | --- | --- |
| BrSE / note author | Capture source material, clarify intent and provide business context | Sole gold annotator for cases they authored |
| Project coordinator / PM | Track decisions, requests, commitments, risks and project continuity | Authority to silently rewrite semantic gold |
| Technical BA / business analyst | Review candidate meaning, evidence and requirement interpretation | An automatic ontology authority |
| Tech lead / domain reviewer | Assess technical feasibility, impact, contradiction and useful retrieval | A substitute for independent annotation across all slices |
| Project owner / business approver | Select journeys, approve G0/G6 claims and accept residual risks | A reviewer of every individual case by default |
| Semantic reviewer | Adjudicate ontology reuse versus semantic gaps and review metric meaning | A person allowed to force-fit unsupported concepts |
| Data/annotation lead | Manage annotator qualification, independence, custody and adjudication records | The model or case author acting as sole labeler |
| Projecta operator/administrator | Operate configured environments and preserve audit/custody controls | A business annotator or holder of sealed test gold |

The G6 reviewer study must include at least three qualified target-role
reviewers, while the broader annotation process remains independent of the
model that drafted any model-assisted case.

## 6. Observable business outcomes (S12-05)

| Journey | Useful outcome | Harmful outcome | Incomplete outcome | Correct abstention |
| --- | --- | --- | --- | --- |
| Structured capture | Typed source and evidence are preserved and reviewable | Wrong project/type or silently altered source | Missing item/evidence or unusable review state | Refuse unsupported cross-project or invalid input |
| Untyped extraction | Minimal-span, correctly typed, linked proposals with provenance | Hallucinated entity/link, over-extraction or direct assertion | Missing supported concept, weak evidence or unusable candidate | Ambiguous/speculative content produces no unsafe candidate |
| Review/correction | Reviewer reaches correct disposition with low effort and retained history | Confirmation of a wrong or unsupported fact | Candidate requires major manual reconstruction | Reject when evidence cannot support a defensible decision |
| Requirement/decision change | Current and historical states, supersession and rationale remain clear | Old fact overwritten or contradiction hidden | Timeline or impact relationship is incomplete | Abstain when change order/evidence is insufficient |
| Requests/commitments/risks | Correct distinction supports coordination and risk visibility | Discussion becomes false commitment, task or risk | Correct class but missing scope/actor/evidence | Leave unsupported intent unclassified |
| Grounded questions | Correct, complete-enough answer with source citations | Invented fact, stale answer or cross-project disclosure | Partial answer presented as complete | Explicitly state ambiguity, no evidence or unsupported intent |
| Ambiguity/hostility/isolation | Safe rejection with no semantic mutation or disclosure | Prompt injection, fabricated link, leak or partial write | Safe error lacks useful diagnosis for the reviewer | Reject untrusted instructions and unsupported targets |
| Longitudinal episode | Reviewable project memory tracks updates and decisions over time | Temporal collapse, duplicate assertion or provenance loss | Some checkpoints or reviewer context are missing | Abstain on unresolved contradiction or unavailable history |

Acceptance must score semantic quality, business utility, safety and operations
separately. A high pooled quality score cannot compensate for a harmful hard-
invariant failure.

## 7. Competency questions and checkpoints (S12-06)

The following questions are the G0 set. G1 may refine wording and define exact
gold schemas, but may not remove a priority journey without a recorded scope
decision.

| ID | Competency question | Journey | Checkpoint |
| --- | --- | --- | --- |
| CQ-01 | What source note and evidence span support each captured item? | 1 | Source/candidate |
| CQ-02 | Does each structured item have the intended type, project and author? | 1 | Candidate/review |
| CQ-03 | Which entities and relations are supported by this untyped note? | 2 | Extraction/candidate |
| CQ-04 | Which concepts require abstention because they are ambiguous, unsupported or unsafe? | 2/7 | Extraction/error |
| CQ-05 | What did the reviewer change, confirm or reject, and why? | 3 | Review/provenance |
| CQ-06 | Which asserted facts were produced, and can each be traced to source and reviewer? | 3 | Asserted/provenance |
| CQ-07 | What is the current requirement or decision, and what did it supersede? | 4 | Longitudinal graph |
| CQ-08 | What evidence explains the requirement change or contradiction? | 4 | Timeline/retrieval |
| CQ-09 | Is this text a request, commitment, task, risk, blocker, assumption or unsupported discussion? | 5 | Candidate/review |
| CQ-10 | Which open questions or risks block the relevant work, and what is their evidence? | 5 | Asserted/inferred/retrieval |
| CQ-11 | What is the answer to a supported project question, and which citations support every fact? | 6 | Retrieval |
| CQ-12 | When evidence is missing, stale, conflicting or cross-project, does the answer abstain or qualify correctly? | 6/7 | Retrieval/error |
| CQ-13 | Does hostile or provider-supplied text change policy, create a link, or mutate semantic state? | 7 | Hard-invariant run |
| CQ-14 | Can a project observe another project's identifiers, evidence, candidates or answers? | 7 | Isolation run |
| CQ-15 | At each episode checkpoint, are source, candidate, asserted, inferred and provenance states correct? | 8 | Scenario graph |
| CQ-16 | Can a target-role reviewer understand and trust the episode well enough to act? | 8 | Blinded business review |

## 8. Claims and non-claims (S12-07)

### Claim eligible for G6 approval

Subject to the later gates, the strongest claim Sprint 12 may approve is:

> On the approved Sprint 12 benchmark and named model/prompt/tool configuration,
> Projecta produces reviewable project knowledge with the recorded semantic,
> business, safety, latency and cost results.

### Explicit non-claims

Sprint 12 must not claim any of the following without a separately approved
evidence boundary:

- universal correctness or readiness for every tenant, domain, language or
  provider;
- production capacity, availability, SLA or cost predictability;
- live Teams readiness or a general connector capability;
- private or authenticated GitHub access, webhooks or continuous sync;
- autonomous requirement, task, deadline or outbound-action decisions;
- ontology completeness; unsupported concepts must remain explicit gaps;
- tenant readiness based only on synthetic/de-identified data;
- quality based only on schema validity, pooled F1, one reviewer or one live
  probe; or
- improvement caused by inspecting or repeatedly tuning against held-out data.

If no authorized tenant-like data is available, G6 may approve only a bounded
synthetic/de-identified benchmark claim with its external-validity limitation.

## 9. Data-source feasibility (S12-08)

| Source option | Feasibility | Approved use at G0 | Constraint |
| --- | --- | --- | --- |
| Human-authored synthetic project cases | High | Primary source for atomic and longitudinal development/validation/test cases | Must be based on approved journeys, independently annotated and provenance-recorded |
| Model-assisted drafts rewritten by humans | Medium | Supplement only after human rewriting and independent annotation | Model origin must be labeled; draft model cannot be sole annotator/adjudicator |
| De-identified authorized project material | Conditional | Permitted only when owner, consent, license, retention and de-identification are documented | No assumption that work-tenant data is available; raw sensitive payload stays out of Git and agent-visible artifacts |
| Public/licensed material | Conditional | Permitted only where license and transformation provenance are clear | Must not be treated as representative tenant data without evidence |
| Current work tenant or personal production data | Not approved | None | Do not acquire, copy, prompt, log or commit it for Sprint 12 |

Language feasibility is a hard constraint. Vietnamese, English and Japanese
cases require qualified annotators; mixed/code-switched cases require a
documented language policy. A language slice without qualified coverage must be
removed or reduced explicitly at G1, not weakly labeled.

The proposed initial corpus targets from the sprint plan remain provisional
until G1 confirms authoring capacity, qualified annotation and privacy review:
at least 200 atomic cases and 24 longitudinal episodes, with development and
validation available to the evaluation workflow and the held-out test split
kept under human custody.

## 10. G0 acceptance checklist (S12-09)

- [x] Released v0.6.0 evaluation boundary is recorded, including inherited
  Sprint 5/6 limitations.
- [x] One buyer-facing hypothesis and bounded strongest claim are recorded.
- [x] Eight priority journeys are ranked.
- [x] Author, reviewer, consumer, approver, semantic, data and operator roles
  are separated.
- [x] Useful, harmful, incomplete and abstained outcomes are defined.
- [x] Sixteen competency questions are bound to explicit checkpoints.
- [x] Release claims and non-claims are explicit.
- [x] Data-source feasibility, language qualification and custody constraints
  are explicit.
- [x] Project owner approves the business scope without revisions.

## 11. Approval record (S12-10)

| Field | Decision |
| --- | --- |
| G0 outcome | `APPROVED` |
| Reviewer | Project owner — explicit approval recorded in Codex task on 2026-08-14 |
| Reviewed artifact digest | Bound by the commit containing this approval record |
| Approved scope revisions | None |
| Conditions for G1 | Preserve the eight journeys, role separation, bounded claims, qualified annotation, privacy/provenance controls and held-out custody unless a new human scope decision is recorded |

The project owner approved all G0 checklist items without revision. Approval of
G0 authorizes dataset-contract design only. It does not approve
the dataset, annotation quality, ontology changes, model choice, optimization,
held-out access or a product release.
