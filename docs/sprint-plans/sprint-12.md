# Sprint 12 Plan — Business Semantic Quality and Evaluation

Status: `G3.1_REMEDIATION_REQUIRED_G5_PAUSED`

G0 packet: [Business Scope Review Packet](sprint-12/g0-business-scope.md)

Remaining-agent handoffs: [Sprint 12 Remaining-Agent Handoffs](sprint-12/agent-handoffs.md)

G4 packet: [Baseline Evaluation Review Packet](sprint-12/g4-baseline.md)

G4.1 packet: [Contract Alignment and Failure Diagnosis](sprint-12/g4.1-contract-alignment.md)

G5 packet: [Controlled Optimization Review Packet](sprint-12/g5-optimization.md)

G6 packet: [Held-out Business Evaluation Packet](sprint-12/g6-business-evaluation.md)

Release target: none until G6 business-quality acceptance and G7 closure decide
whether a product release is justified.

## Sprint Goal

Prove, with a governed and leakage-resistant benchmark, how reliably Projecta
turns realistic BrSE project material into useful, reviewable, evidence-backed
knowledge before adding more connector or outbound-action breadth.

## Why This Sprint Exists

Projecta `v0.6.0` has strong runtime, isolation, provenance, review, recovery,
and release boundaries. Its current Sprint 5 semantic-quality dataset, however,
contains only eight synthetic sentence-level cases with one case per slice.
That suite is valuable contract evidence, but it does not establish realistic
business usefulness, longitudinal graph quality, ontology coverage, reviewer
effort, multilingual behavior, calibration, latency, or cost.

Sprint 12 therefore pauses new connector breadth and creates a repeatable
evaluation flywheel:

```text
business journeys
→ governed dataset
→ independent human gold
→ frozen baseline
→ error taxonomy
→ prompt/agent/tool experiments
→ sealed held-out evaluation
→ business acceptance
```

After the immutable S12-f-07 and S12-f-08 experiments, a direct evidence audit
found that the repository-visible corpus is suitable as a contract fixture but
not yet as the business benchmark promised by this sprint. Sprint 12 therefore
remains open and inserts a non-destructive G3.1 remediation gate before further
provider optimization, candidate selection, validation, or G6. Historical G3,
G4, G4.1, and G5 decisions remain unchanged and are not relabeled.

## Business Hypothesis

For BrSE, project coordinator, business analyst, project manager, and technical
lead workflows, Projecta should reduce the effort needed to turn fragmented
project notes into traceable knowledge while preserving human control. Evidence
must show that users can review, correct, retrieve, and trust the result; a
schema-valid model response alone is not sufficient.

The strongest claim this sprint may approve is:

> On the approved Sprint 12 benchmark and named model/prompt/tool
> configuration, Projecta produces reviewable project knowledge with the
> recorded semantic, business, safety, latency, and cost results.

This claim does not generalize to every tenant, language, domain, provider, or
production workload. G6 may approve a tenant-pilot claim only when authorized
pilot evidence is present; otherwise it may approve only a bounded
synthetic/de-identified benchmark claim.

## In Scope

- Manual structured Quick Note and LLM-assisted untyped Quick Note journeys.
- Candidate entities, relations, bounded links, abstention, evidence, review,
  confirmation/rejection, graph projection, and grounded project questions.
- Realistic single-note inputs and longitudinal project episodes.
- Vietnamese, English, Japanese, and mixed/code-switched project language,
  subject to qualified annotation at G1.
- Requirement discovery and change, decisions and supersession, requests
  versus committed tasks, risks and blockers, assumptions and constraints,
  progress claims, contradictions, ambiguity, duplicates, and hostile text.
- Dataset provenance, privacy, licensing, annotation agreement, leakage
  control, reproducible evaluation, error analysis, latency, and cost.
- Optimization of prompts, bounded context, agent workflow, and tools only
  after the baseline and split boundaries are frozen.

## Dataset Architecture

### Atomic Note Benchmark

The first frozen version targets at least 200 independently addressable inputs:

- At least 80 Vietnamese cases, 40 English cases, 20 Japanese cases, and 20
  mixed/code-switched cases; remaining cases follow the G1 coverage gaps.
- At least 30 explicit ambiguity or correct-abstention cases.
- At least 20 adversarial, prompt-injection, isolation, or fabricated-link
  cases.
- All released candidate types and supported relation/link predicates have
  positive, negative, boundary, and confusable examples.
- At least 60% of cases are human-authored from approved business scenarios.
  Model-assisted cases are labeled as such and require human rewriting and
  independent annotation.

### Longitudinal Scenario Benchmark

The first frozen version targets at least 24 project episodes. Each episode has
5–12 ordered events, expected review decisions, expected graph checkpoints, and
grounded competency-question answers. G0 selects no more than eight priority
journeys, and the set must cover at least three episodes for each, including temporal change,
contradiction, duplicate evidence, and cross-project counterexamples.

### Dataset Splits and Custody

- Atomic cases use a stratified 60% development, 20% validation, and 20% test
  split.
- Scenario cases use 12 development, 6 validation, and 6 test episodes.
- Development data is available for diagnosis and optimization. Validation
  data is used only for candidate selection after an experiment is registered.
- Test inputs and gold remain under human custody outside the agent-visible
  repository until G6. The repository records only schema, counts, split policy,
  and cryptographic digests before unsealing.
- Test results remain valid only when the evaluated code, prompt, model,
  ontology, dataset, configuration, and result artifacts are digest-bound.

### Annotation and Adjudication

- Every validation and test item is independently annotated by two qualified
  annotators; at least 25% of development items are double-annotated.
- A third qualified reviewer adjudicates every material disagreement in the
  validation and test splits.
- The pilot must achieve provisional agreement of at least `0.80` for typed
  classification/abstention, span F1 of at least `0.85`, relation/link F1 of at
  least `0.80`, and scenario graph-state agreement of at least `0.80`.
- G1 may revise a provisional threshold once with a written rationale. No
  threshold or scoring rule may change after G3 without invalidating the frozen
  benchmark version.
- A concept unsupported by the released ontology is labeled as a semantic gap;
  annotators must not force-fit it to the nearest released term.

## Metric Hierarchy

### Hard Invariants

Every evaluated run must satisfy all of these at 100%; aggregate quality cannot
compensate for a failure:

- Schema validity and bounded provider output.
- Source evidence integrity and Unicode code-point bounds.
- Server allowlists; no model-created RDF, IRI, predicate, graph, or target ID.
- Project isolation and no cross-project existence disclosure.
- Required source, candidate, activity, and decision provenance.
- SHACL conformance for every persisted positive case.
- No extraction-time write to asserted or inferred graphs.
- Fail-explicit behavior with no partial semantic mutation.
- Dataset provenance, split integrity, digest binding, and holdout non-leakage.

### Semantic Quality Thresholds

Unless G1 approves a justified revision before G3, the G6 held-out gate uses:

- Entity-type macro F1 `>= 0.80`.
- Relation macro F1 `>= 0.75`.
- Bounded entity-link F1 `>= 0.80`.
- Gold evidence-span exact match `>= 0.95`.
- Abstention precision and recall each `>= 0.90`.
- Released-ontology mapping accuracy `>= 0.85` on mappable gold items.
- Scenario checkpoint graph accuracy `>= 0.80`.
- Grounded answer factual correctness `>= 0.85`, citation correctness `1.00`,
  and completeness `>= 0.80` on answerable competency questions.
- Every gold concept is either mapped correctly or recorded as an adjudicated
  ontology gap; silent loss is not allowed.

### Business and Operational Thresholds

- At least 70% of proposed candidates are accepted without semantic correction.
- At least 85% are accepted unchanged or with a predefined minor correction.
- Median review time is at least 30% lower than the measured manual-structuring
  baseline, with the same business questions and quality rubric.
- At least three target-role reviewers evaluate at least 12 blinded scenario
  journeys under a randomized, counterbalanced protocol and give median
  usefulness and trust scores of at least 4/5.
- P50/P95 latency, input/output tokens, configured cost, abstention rate, and
  accepted-candidate cost are reported by slice and configuration. G6 cannot
  claim production capacity from this bounded benchmark.

## Gate Model

| Gate | Decision | Blocking evidence | Authority |
| --- | --- | --- | --- |
| G0 — Business Scope | Are the personas, priority journeys, competency questions, and allowed claims worth evaluating? | Business contract, journey ranking, non-goals, data-source feasibility | Project owner |
| G1 — Dataset Contract | Can data be created and scored safely and reproducibly? | Schema, coverage matrix, annotation guide, privacy/provenance policy, split/custody design, metrics, ontology gap audit | Project owner plus semantic reviewer |
| G2 — Annotation Pilot | Can independent humans apply the rubric consistently? | Pilot corpus, independent labels, agreement report, adjudication log, revised guide | Project owner plus annotation lead |
| G3 — Dataset Freeze | Is the full corpus sufficiently covered, clean, licensed, non-leaking, and immutable? | Validator report, coverage report, privacy scan, duplicate/leakage report, manifests and digests | Project owner plus data reviewer |
| G4 — Baseline | Is the current `v0.6.0` semantic path measured truthfully before optimization? | Reproducible baseline report, hard-invariant results, slice metrics, cost/latency, error taxonomy | Project owner |
| G5 — Optimization Freeze | Is one candidate configuration better without hidden regression or test exposure? | Registered experiments, development/validation comparisons, invariant suite, frozen candidate digests | Project owner plus technical reviewer |
| G6 — Held-out Business Quality | Does the frozen candidate meet semantic and business thresholds on blinded data? | Human-unsealed run, held-out metrics, reviewer study, manual baseline, ontology-gap disposition | Project owner plus business and semantic reviewers |
| G7 — Sprint Closure | What can Projecta truthfully claim and what work follows? | Reproducibility packet, dataset/model cards, regression evidence, residual risks, release recommendation | Project owner |

A gate is not passed by completing its tasks. Its approval record must identify
the exact artifacts and digests reviewed. A rejected gate reopens only the
tasks needed to address its recorded findings; evidence is never relabeled.

## Atomic Tasks

Status legend: `[ ]` pending / `[~]` in progress / `[x]` done

### Phase A — Business Contract and G0

- [x] **S12-01 — Audit the released evaluation surface:** Record the exact
  Quick Note, extraction, review, graph, retrieval, ontology, and Sprint 5/6
  evaluation boundaries inherited from `v0.6.0`.
- [x] **S12-02 — Define the buyer-facing hypothesis:** State the business value
  to prove for BrSE and tenant project teams without making a universal claim.
- [x] **S12-03 — Rank priority business journeys:** Select and order no more
  than eight journeys that the Sprint 12 benchmark must represent.
- [x] **S12-04 — Define target roles:** Specify author, reviewer, consumer, and
  administrator responsibilities for each selected journey.
- [x] **S12-05 — Define business outcomes:** Describe the observable useful,
  harmful, incomplete, and abstained outcomes for each journey.
- [x] **S12-06 — Define competency questions:** Write the questions each
  scenario graph and retrieval result must answer at named checkpoints.
- [x] **S12-07 — Define release claims and non-claims:** Bound language around
  tenant readiness, provider generalization, languages, and production scale.
- [x] **S12-08 — Assess data-source feasibility:** Identify synthetic,
  human-authored, and authorized de-identified sources without acquiring data.
- [x] **S12-09 — Prepare the G0 packet:** Bind S12-02 through S12-08 into one
  reviewable business-scope artifact.
- [x] **S12-10 — Approve G0 business scope:** Human accepts, revises, or rejects
  the benchmark purpose before dataset design proceeds.

### Phase B — Dataset Contract and G1

G1 packet: [Dataset Contract Review Packet](sprint-12/g1-dataset-contract.md)

- [x] **S12-11 — Define the case envelope:** Specify stable IDs, source text,
  origin, language, sensitivity, license, scenario, split, and version fields.
- [x] **S12-12 — Define the atomic gold schema:** Specify entities, relations,
  links, evidence spans, abstention, ambiguity, and semantic-gap labels.
- [x] **S12-13 — Define the scenario gold schema:** Specify ordered events,
  review decisions, graph checkpoints, temporal expectations, and expected
  competency-question answers.
- [x] **S12-14 — Define the correction taxonomy:** Separate unchanged,
  formatting-only, minor semantic, major semantic, rejected, and missing output.
- [x] **S12-15 — Define the coverage matrix:** Cross priority journey, semantic
  class, language, source style, ambiguity, temporal behavior, and threat slice.
- [x] **S12-16 — Freeze minimum quotas:** Record the approved corpus sizes,
  language mix, scenario counts, and human/model-assisted origin limits.
- [x] **S12-17 — Define annotation guidance:** Write decision rules and
  counterexamples for spans, types, relations, links, abstention, and gaps.
- [x] **S12-18 — Define annotator qualifications:** Specify language and domain
  competence, independence, conflicts, and adjudicator authority.
- [x] **S12-19 — Define provenance and licensing policy:** Require an auditable
  origin and permitted use for every case without storing sensitive payloads.
- [x] **S12-20 — Define privacy and retention policy:** Specify consent,
  de-identification, prohibited data, review, deletion, and breach handling.
- [x] **S12-21 — Threat-model dataset leakage:** Cover duplicates, near
  duplicates, prompt contamination, model memorization, and holdout exposure.
- [x] **S12-22 — Define split and custody procedure:** Specify stratification,
  human custody, digest publication, unlock, invalidation, and resealing.
- [x] **S12-23 — Define dataset validation rules:** Specify schema, offset,
  coverage, provenance, duplicate, split, and referential-integrity failures.
- [x] **S12-24 — Define metric implementations:** Freeze formulas, averaging,
  confidence intervals, missing-output handling, and slice aggregation.
- [x] **S12-25 — Pre-register quality thresholds:** Record hard, semantic,
  business, and operational gate values before the full dataset is observed.
- [x] **S12-26 — Audit ontology reuse and gaps:** Use the governed ontology
  workflow to classify required concepts as released reuse, operational state,
  or proposed semantic change.
- [x] **S12-27 — Prepare the G1 packet:** Bind the complete dataset, annotation,
  metrics, privacy, custody, and semantic contracts.
- [x] **S12-28 — Approve G1 dataset contract:** Human and semantic reviewers
  accept, revise, or reject the frozen design before authoring at scale.

### Phase C — Annotation Pilot and G2

G2 packet: [Annotation Pilot Review Packet](sprint-12/g2-annotation-pilot.md)

Owner-delegated amendment: the project owner delegated semantic review of the
repository-visible synthetic track to the implementation agent. S12-32 through
S12-37 are complete for that AI-reviewed track only. Their evidence remains
`humanEvidence: false` and cannot support inter-human reliability, tenant or
production-readiness claims.

G3 packet: [Dataset Freeze Review Packet](sprint-12/g3-dataset-freeze.md)

- [x] **S12-29 — Author the pilot atomic set:** Create at least 20 cases spanning
  priority types, ambiguity, multilingual text, and adversarial input.
- [x] **S12-30 — Author the pilot scenario set:** Create at least three
  longitudinal episodes with graph checkpoints and business questions.
- [x] **S12-31 — Validate pilot source provenance:** Confirm every pilot case is
  permitted, classified, and free of prohibited content.
- [x] **S12-32 — Calibrate annotators:** Execute the owner-delegated AI
  calibration protocol without accessing held-out payload or gold.
- [x] **S12-33 — Review the pilot labels:** Preserve two isolated logical
  fixture passes and complete an owner-delegated AI semantic review; do not
  claim independent-human annotation.
- [x] **S12-34 — Measure pilot evidence:** Recompute applicable fixture
  agreement and record scenario/competency single-review conformance separately
  from unavailable inter-annotator agreement.
- [x] **S12-35 — Adjudicate pilot disagreements:** Record the accepted outcome
  and reason for every material disagreement.
- [x] **S12-36 — Revise the annotation guide:** Correct only ambiguous rules
  revealed by the pilot and version the changes.
- [x] **S12-37 — Re-run revised guidance:** Apply guide v1.1 to 12 disjoint
  development cases and record AI semantic conformance without relabeling it as
  inter-human agreement.
- [x] **S12-38 — Prepare the draft G2 packet:** Bind pilot cases, fixture labels,
  metrics, adjudication, and guide versions.
- [x] **S12-39 — Approve G2 annotation reliability:** Human reviewers accept,
  revise, or reject scaled dataset production.

### Phase D — Corpus Construction and G3

The repository-visible development/validation gold uses the same
owner-delegated AI-review amendment. It has complete digest-bound semantic
review but no independent-human evidence; the held-out custody task remains
unchanged and blocking.

- [x] **S12-40 — Author the atomic development pool:** Create the
  agent-authored synthetic core authorized by the owner-delegated amendment.
- [x] **S12-41 — Author ambiguity and abstention slices:** Add confusable,
  incomplete, social, speculative, and unsupported cases.
- [x] **S12-42 — Author adversarial and isolation slices:** Add prompt injection,
  fabricated links, cross-project references, and untrusted instructions.
- [x] **S12-43 — Author multilingual and noisy slices:** Add approved Vietnamese,
  English, Japanese, shorthand, typo, and code-switched cases.
- [x] **S12-44 — Author longitudinal episodes:** Create the full ordered scenario
  set with temporal updates, contradictions, duplicates, and review decisions.
- [x] **S12-45 — Annotate atomic semantic gold:** Produce evidence, type,
  relation, link, abstention, ambiguity, and gap annotations.
- [x] **S12-46 — Annotate scenario graph gold:** Produce expected source,
  candidate, asserted, inferred, and provenance checkpoints.
- [x] **S12-47 — Annotate retrieval gold:** Produce expected facts, citations,
  completeness, freshness, contradiction, and abstention outcomes.
- [x] **S12-48 — Annotate business-review gold:** Record expected reviewer
  disposition and correction severity without prescribing subjective timing.
- [x] **S12-49 — Complete synthetic-track QA:** Review and digest-bind all 160
  repository-visible atomic cases and 18 scenarios; independent-human QA and
  hidden-test annotation are explicitly not claimed.
- [x] **S12-50 — Adjudicate repository-visible gold:** Resolve the synthetic
  development/validation gold under owner-delegated AI adjudication and version
  the decision log; held-out and inter-human adjudication remain outside scope.
- [x] **S12-51 — Run privacy and provenance validation:** Fail on prohibited,
  unlicensed, untraceable, or insufficiently de-identified material.
- [x] **S12-52 — Run coverage validation:** Fail when any approved quota or
  business journey is missing.
- [x] **S12-53 — Run duplicate and leakage validation:** Detect exact and near
  duplicates across splits and remove or reassign contaminated cases.
- [x] **S12-54 — Freeze development and validation splits:** Publish versioned
  manifests and immutable content digests.
- [ ] **S12-55 — Seal the test split:** Move inputs and gold to human custody and
  publish only counts, schema version, and cryptographic digests.
- [x] **S12-56 — Prepare the draft G3 packet:** Bind validation, coverage, privacy,
  provenance, agreement, leakage, manifest, and custody evidence.
- [x] **S12-57 — Approve G3 dataset freeze:** Human data and semantic reviewers
  accept the exact dataset version or require a new version.

### Phase E — Evaluation Harness, Baseline, and G4

- [x] **S12-58 — Implement the versioned dataset loader:** Reject unknown schema,
  missing provenance, invalid references, and split-policy violations.
- [x] **S12-59 — Implement dataset integrity checks:** Validate offsets, IDs,
  quotas, digests, duplicates, and cross-file references deterministically.
- [x] **S12-60 — Implement extraction metrics:** Score types, relations, links,
  spans, abstention, hallucination, and calibration by slice.
- [x] **S12-61 — Implement ontology-mapping metrics:** Score released-term
  mapping, semantic gaps, SHACL conformance, and prohibited vocabulary output.
- [x] **S12-62 — Implement scenario graph metrics:** Compare graph checkpoints,
  temporal state, contradictions, provenance, and project scope.
- [x] **S12-63 — Implement retrieval metrics:** Score factual correctness,
  citations, completeness, freshness, and appropriate abstention.
- [x] **S12-64 — Implement reviewer utility capture:** Record disposition,
  correction class, review time, usefulness, and trust without raw sensitive data.
- [x] **S12-65 — Implement operational metrics:** Record latency, usage, cost,
  failure class, and accepted-candidate cost by configuration and slice.
- [x] **S12-66 — Implement the evidence report:** Emit version/digest-bound JSON
  and Markdown without hidden case omission or pooled-only summaries.
- [x] **S12-67 — Add evaluator self-tests:** Prove tamper, malformed gold,
  missing output, duplicate, leakage, and metric edge cases fail explicitly.
- [x] **S12-68 — Run the `v0.6.0` baseline:** Evaluate the released prompt and
  runtime configuration on development and validation without changing them.
- [x] **S12-69 — Classify baseline errors:** Produce a finite taxonomy covering
  data, annotation, ontology, prompt, context, tool, model, and runtime causes.
- [x] **S12-70 — Prepare the draft G4 packet:** Bind baseline configuration, results,
  hard invariants, slice metrics, cost/latency, and error taxonomy.
- [x] **S12-71 — Approve G4 baseline with limitations:** Human accepts the
  measurement as truthful; runtime-backed baseline and optimization remain gated.
  before any optimization result is considered.

### Phase F — Controlled Optimization and G5

S12-f-07 and S12-f-08 are immutable rejected experiments. The remaining
generic context, workflow, and tool experiments plus S12-78 through S12-81 are
paused until the G3.1 remediation track below passes. This pause does not
rewrite the historical G3 or G5 approvals and does not authorize held-out
access.

- [x] **S12-72 — Create the experiment registry:** Require a hypothesis,
  permitted split, configuration digest, metric target, and stopping rule.
- [x] **S12-73 — Run prompt experiments:** Change only the versioned prompt
  package and record development results; the supersession guard improved the
  8-case slice but the 32-case follow-up still has schema failures, so no
  candidate is selected.
- [ ] **S12-74 — Run context experiments:** Change only bounded retrieval/context
  selection and record development results.
- [ ] **S12-75 — Run agent-workflow experiments:** Change only orchestration or
  decomposition while preserving policy and semantic authority boundaries.
- [ ] **S12-76 — Run tool experiments:** Change only allowlisted tool behavior
  and record calls, failures, latency, and semantic impact.
- [x] **S12-77 — Run model comparisons:** Stage A ran `deepseek-v4-pro` versus
  `deepseek-v4-flash` on 16 development cases × 3 paired runs. The candidate
  hard gate passed but control failed; semantic gates failed, so no Stage B or
  candidate selection is authorized.
- [x] **S12-f-07 preparation — Build the development error backlog:** All 288
  persisted S12-73/S12-77/S12-f-06 report executions were accounted with 17
  fail-explicit missing outputs. The backlog approves one relation-focused
  prompt hypothesis on `deepseek-v4-flash`; Stage A execution remained deferred
  until the execution package was frozen.
- [x] **S12-f-07 execution package freeze:** Prompt, evaluator instrumentation,
  interleaved temporal pairing, fail-closed accounting, digest preflight and
  mocked runner custody were committed at `2b8ca5a`; no provider call was made.
- [x] **S12-f-07 Stage A authorization:** Authorization v1 remains immutable
  pending history; authorization v2 binds registry/G5 v7 and the frozen commit.
  Stage A was executed once and is now closed as `COMPLETED_REJECTED`; pricing
  remained required before selection and Stage B.
- [x] **S12-f-07 closure and scoring erratum:** Preserve the aggregate and six
  report digests unchanged, record corrected entity metrics and provisional
  relation measurement, and prohibit Stage B and candidate selection.
- [x] **S12-f-08 preparation:** Open a new prompt-only experiment with composed
  v5, canonical relation endpoints, positive-relation floors/deltas, zero
  supersession false positives, evaluator v2, cache-aware pricing and a
  frozen guarded runner. Registry/G5 v9 and authorization v2 bound the
  execution-package commit. Stage A ran exactly once with 96/96 case-runs and
  failed the positive-relation gates; Registry/G5 v10 close it rejected with no
  Stage B or candidate selection.

#### Phase F-R1 — Measurement Remediation and G3.1-A

- [x] **S12-R01 — Publish the core-quality audit:** Bind the observed corpus,
  scenario, metric, f08, and evaluator evidence without changing any historical
  report or approval.
- [x] **S12-R02 — Version the metric contract:** Separate relation semantic
  correctness `(predicate, canonical source, canonical target)` from relation
  evidence support and exact-span quality; freeze formulas and denominators
  before new provider execution.
- [x] **S12-R03 — Repair relation error buckets:** Make diagnostic categories
  mutually exclusive or explicitly directional so a wrong-span prediction is
  not misreported as an additional predicate error.
- [x] **S12-R04 — Persist sanitized diagnostic signatures:** Record per-case
  predicates, canonical endpoint signatures, offsets, and error classes without
  raw source text, credentials, or sensitive payloads.
- [x] **S12-R05 — Strengthen near-duplicate leakage validation:** Canonicalize
  generator markers, numeric IDs, punctuation, and scenario lineage; block
  normalized template overlap across development, validation, and test.
- [x] **S12-R06 — Validate language metadata:** Detect and adjudicate source
  language mismatches and remove any language slice without qualified review.
- [x] **S12-R07 — Validate scenario semantic consistency:** Reject repeated
  source sequences with unexplained conflicting temporal effects, review
  dispositions, checkpoints, or competency answers.
- [x] **S12-R08 — Approve G3.1-A measurement readiness:** Bind evaluator tests,
  corpus-lint tests, metric definitions, and residual limitations; provider
  execution remains blocked until approval.

#### Phase F-R2 — Dataset v3 Deep Pilot and G3.1-B

- [x] **S12-R09 — Author the v3 atomic deep pilot:** Create 48–64 natural Quick
  Notes from distinct business storylines without evidence markers, sequence
  filler, or ID-only paraphrases; preserve origin and permission metadata.
- [x] **S12-R10 — Author the v3 longitudinal pilot:** Create six unique episodes
  with explicit actors, chronology, updates, contradictions, review decisions,
  graph checkpoints, and competency questions; keep each lineage in one split.
- [x] **S12-R11 — Annotate and adjudicate v3 pilot gold:** Apply the versioned
  evidence, type, relation, abstention, temporal, retrieval, and correction
  rules under owner-delegated AI review while retaining `humanEvidence: false`.
- [x] **S12-R12 — Run the v3 pilot quality gate:** Require zero schema,
  provenance, span-integrity, language, scenario-consistency, and split-leakage
  failures; publish type, predicate, positive/negative, abstention, and business-
  journey coverage instead of relying on total case count.
- [x] **S12-R13 — Approve G3.1-B pilot quality:** Review representative cases,
  gold rationales, normalized-template clusters, scenario timelines, and metric
  computability before authorizing scale-up.

#### Phase F-R3 — Dataset v3 Scale, Freeze, and G3.1-C

- [x] **S12-R14 — Scale the approved v3 patterns:** Expand only pilot patterns
  that passed G3.1-B, maintaining natural variation, relation-positive depth,
  hard negatives, language policy, and lineage-disjoint splits.
- [x] **S12-R15 — Freeze dataset v3:** Publish new atomic/scenario payloads,
  gold, manifests, digests, coverage, privacy, provenance, leakage, and QA
  evidence while preserving v1/v2 unchanged as historical fixtures.
- [x] **S12-R16 — Approve G3.1-C dataset readiness:** Confirm v3 is suitable for
  controlled development and one validation run; test custody and held-out
  access remain separate and blocked.

#### Phase F-R4 — Deterministic Relation Evidence Tool and G5-R

- [x] **S12-R17 — Supersede stale generic preregistrations:** Close or version
  S12-f-02 through S12-f-04 entries bound to the old manifest before opening a
  v3 experiment; never mutate their historical records.
- [x] **S12-R18 — Implement a server-owned relation evidence materializer:** Use
  canonical entity spans, predicate output, an optional trigger quote, and
  deterministic clause/sentence boundaries instead of relying on LLM-authored
  offsets or arbitrary relation-span boundaries.
- [x] **S12-R19 — Add offline materializer regressions:** Cover multilingual
  punctuation, repeated mentions, code points, multiple entities, ambiguous
  clauses, missing triggers, and fail-closed non-materialization.
- [x] **S12-R20 — Preregister S12-f-09:** Change only the `tool` dimension on v3,
  retain `deepseek-v4-flash` and the accepted control prompt, bind pricing and
  digests, use paired interleaving, and prohibit retries, held-out access, and
  prompt/model sweeps.
- [x] **S12-R21 — Authorize S12-f-09 Stage A:** Require G3.1-A/B/C approval,
  clean preflight, exact execution-package digests, explicit cost ceiling, and
  owner authorization before any provider call.
- [x] **S12-R22 — Execute S12-f-09 Stage A once:** Run the preregistered v3
  development subset, preserve every case-run, and report semantic relation,
  evidence, entity, abstention, hallucination, stability, latency, and cost
  separately.
- [x] **S12-R23 — Decide S12-f-09 Stage B:** Issue the offline scoring erratum
  and close f09 as rejected in Registry/G5 v11. The fail-closed report records
  attempted versus valid case-runs, pooled evidence denominators, the
  unevaluated slice-floor gate, and degraded causal attribution from independent
  provider outputs. Stage B remains closed and no candidate is selected.

#### G3.1 and G5-R Gate Conditions

| Gate | Required evidence before approval |
| --- | --- |
| G3.1-A — Measurement | Semantic relation and evidence metrics are separate; diagnostic buckets reconcile without accidental double counting; sanitized signatures support retrospective error analysis; evaluator fixtures pass. |
| G3.1-B — Deep pilot | 48–64 natural atomic cases and six unique scenarios; no artificial evidence markers; zero normalized-template overlap across splits; zero unexplained scenario-gold conflict; language metadata and gold are adjudicated. |
| G3.1-C — Dataset freeze | v3 scales only approved pilot patterns; all lineages stay in one split; v1/v2 remain immutable; schema, provenance, privacy, leakage, semantic QA, coverage, and digest gates pass. |
| G5-R Stage A | Zero schema, evidence-integrity, missing-output, provenance, isolation, or supersession hard failures; proposed preregistration floors are relation semantic F1 ≥ 0.80, relation evidence exact/support ≥ 0.85, entity macro F1 ≥ 0.85, abstention F1 ≥ 0.90, and semantic hallucination rate ≤ 0.05, with no material slice regression. R02 may revise these values only before execution and with an explicit versioned approval. |
| G5-R Stage B and selection | Stage A passes every registered gate; the larger development run confirms stability; validation remains untouched until S12-78 selects exactly one candidate. |

The f09 closure is bound by `optimization/experiment-registry.v11.json` and
`optimization/g5-packet.v11.json`. Its immutable raw aggregate remains v1;
v2 is the prior offline repair; v3 and `s12-f-09-scoring-erratum.v1.*` are the
corrected offline closure artifacts. The f09 authorization commit is retained
as historical metadata because it did not contain the complete execution
package; artifact digests preserve evidence integrity.

#### Phase F-R5 — S12-f-09 Remediation Before New Stage A

The remediation track is open in
`optimization/s12-f-09-remediation-track.v3.*` (v1/v2 remain historical). It does not reopen f09, call a
provider, inspect validation/held-out data, or authorize candidate selection.

- [x] **S12-RM-01 — Prove shared-response pairing offline:** Add the
  provider-agnostic shared-response primitive and mocked digest proof. Full
  runner binding remains part of RM-04.
- [x] **S12-RM-02 — Version slice thresholds:** Freeze slice labels,
  denominators, thresholds, zero-denominator policy, and macro/micro statistic
  in `harness/slice-threshold-contract.v1.*` before the next preregistration.
- [x] **S12-RM-03 — Decide trigger-quote contract:** Require
  predicate-specific `triggerQuote` for the next candidate and fail closed on
  missing/invalid trigger context; bind schema, materializer and tests.
- [x] **S12-RM-04 — Complete the executable package:** Reopen the historical
  scaffold freeze. The draft package and v1 freeze remain immutable historical
  evidence; the v2/v3 lineage was later found to have a false-positive
  reproducibility preflight because corpus and metric inputs were worktree-only.
  RM-04 is now remediated by the v4 package/freeze lineage, which binds every
  runner-read input, exact freeze commit, authorization contract and gate.
- [x] **S12-RM-04A — Freeze the runner implementation:** Prove the 48-call /
  96-branch schedule, identical response digests, fail-closed provider/schema
  errors, separate materializer failures and cache-aware pricing offline. The
  implementation is present and adversarial validation passes.
- [x] **S12-RM-04B — Commit the final package:** Add the final prompt, provider
  response schema, adapter, evaluator, case selection and execution package as
  new versioned artifacts; do not overwrite the draft or v1 freeze.
- [x] **S12-RM-04C — Pass preauthorization preflight:** Recompute the frozen
  corpus profile, slice labels/denominators and blob digests from the bound
  commit; verify output custody, canonical tests, no held-out access and no
  authorization. `PREAUTHORIZATION_READY` is recorded by preflight v2; this
  task remains separate from Approval A/B. The v2 preflight was a false
  positive; preflight v3 now passes the v4 package with corpus/metric blob,
  exact-commit, Approval-A digest, cost-ceiling and invalid-evidence checks.
- [x] **S12-RM-05 — Approval A: issue preregistration and freeze only:** Issue
  the final v4 preregistration and v5 freeze only after RM-04C passes. This
  approval does not authorize provider execution; Approval B is a separate
  owner decision. Approval A is recorded in
  `optimization/s12-f-10-approval-a.v2.json`; provider execution, Stage A,
  Stage B and candidate selection remain unauthorized.
- [x] **S12-RM-06 — Approval B: authorize one bounded Stage A:** Owner-delegated
  review binds Approval A v2, preregistration v4, package/freeze v5, exact
  commit `3a90c4c`, concrete `DeepSeekProviderAdapter`, live non-secret runtime
  digest, fixed output, no-retry policy and exact `$10.00` ceiling. Approval B
  is recorded in `optimization/s12-f-10-approval-b.v1.json`; issuance performs
  no provider call and does not authorize held-out access, Stage B, selection
  or promotion.
- [x] **S12-RM-07 — Execute S12-f-10 Stage A once:** The guarded CLI used
  Approval B v1 exactly once and performed 48 shared provider calls and 96
  branch outputs. The immutable report preserves all 48 `schema_invalid`
  provider outcomes, actual cache-aware cost `$0.0031325392`, zero retries,
  no overwrite, and no held-out access. Stage B and promotion remain closed;
  a separate decision artifact is required for any next governance action.
- [x] **S12-RM-08 — Issue the f10 contract-failure erratum:** Preserve the
  historical report and decision, while correcting the comparison-slice
  interpretation to `NOT_EVALUABLE_SCHEMA_CONTRACT_FAILURE`. The erratum is
  offline-only and does not retry f10 or authorize Stage B.
- [x] **S12-RM-09 — Freeze the S12-f-11 schema canary package:** Bind the
  Pydantic-derived envelope schema v2, prompt v7 examples, four development
  cases, concrete adapter/runtime digests, sanitized diagnostics and exact
  no-retry/output constraints. The package and freeze remain pending a
  separate canary authorization; no provider call is authorized here.
- [ ] **S12-RM-10 — Owner review and execute the S12-f-11 canary:** Requires a
  new digest-bound authorization and exactly four development calls. A `4/4`
  schema-valid result is required before any full Stage A authorization can be
  considered; no f10 authorization may be reused.
- [x] **S12-RM-11 — Remediate the f11 canary contract blockers:** The
  superseding v2 lineage explicitly binds four calls, corrected prompt spans,
  sanitized diagnostics, independent attempt/response/schema/usage/pricing
  counters, and direct authorization constraints for calls, schema-valid
  responses, Stage B, selection and promotion. Freeze v1 at `d869443` remains
  historical and untouched.
- [x] **S12-RM-12 — Re-review and authorize the superseding f11 canary:** Owner
  review verifies package/freeze v2, exact commit `ed08f99`, live non-secret
  runtime digest, four-call cost proof, sanitized diagnostics, independent
  accounting and direct authorization constraints. Authorization v1 permits
  one four-call development canary only; issuance performs no provider call and
  does not open full Stage A, Stage B, selection, validation or held-out access.
- [x] **S12-RM-13 — Execute and review the f11 canary once:** Authorization v1
  was used exactly once for four development calls and eight branch outputs.
  All responses were schema-valid, usage-valid and priced; total cost was
  `$0.0008742944`, with zero retries, no overwrite, no raw payload/source text,
  and no held-out, Stage B, selection or promotion access.
- [x] **S12-RM-14 — Owner review for full Stage A preparation:** The canary
  evidence is accepted as proof that the remediated schema/runtime contract is
  executable. Review status is `APPROVED_TO_PREPARE_FULL_STAGE_A_PACKAGE`, not
  execution authorization; canary authority is not reusable and no full Stage A
  package/freeze currently exists.
- [x] **S12-RM-15 — Prepare and freeze the f11 full Stage A package:** Bind a
  development-only 16-case × 3-run shared-response experiment: 48 provider
  calls, 96 branch outputs, prompt/schema v2 lineage, full semantic evaluator,
  hard/slice gates, sanitized diagnostics, 48-call runtime/cost proof, no retry
  or overwrite, and an exact freeze commit. Package/freeze v1 are bound to the
  exact preparation commit and zero-call preflight passes. No authorization is
  issued here.
- [x] **S12-RM-15A — Remediate the f11 full Stage A execution contract:**
  Preserved v1 as historical evidence and published superseding v2
  preregistration/package/freeze artifacts with one canonical top-level
  `hardGates.invalidEvidence` contract. The v2 guarded runner stages the
  legacy report and persists the final report once; a mocked authorized test
  reaches exactly 48 provider captures and 96 branches without network access.
  Exact-commit, ancestor and bound-Git-blob preflight is required and remains
  zero-call; no provider authorization is issued.
- [x] **S12-RM-16 — Review and authorize full Stage A separately:** Owner review
  accepts the superseding v2 package after exact-commit/blob preflight and the
  48-call/96-branch mocked E2E pass. Authorization v1 binds package/freeze v2,
  commit `55540e4`, the live non-secret runtime digest, fixed output, no retry
  and exact `$10.00` ceiling. Issuance performs no provider call and does not
  authorize validation, held-out, Stage B, selection or promotion.
- [x] **S12-RM-17 — Execute and review f11 full Stage A once:** The corrected
  v3 lineage was executed exactly once under authorization v2: 48 shared
  provider calls and 96 branches, with no retry or overwrite. The report
  records complete usage/pricing and all hard, semantic and slice results;
  invalid-evidence and semantic slice gates failed closed. Decision artifact
  `s12-f-11-full-stage-a-decision.v1.json` records
  `COMPLETED_REJECTED_NO_STAGE_B`; Stage B, selection, validation, held-out and
  promotion remain closed pending a separate owner decision.
- [x] **S12-RM-18 — Offline f11 relation root-cause analysis:** Recomputed the
  frozen gold profile and structural oracle relation ceiling without reading
  raw provider payloads or held-out data. The RCA confirms an entity bottleneck
  signal, zero relation semantic true positives, 53 candidate
  materializer/evidence failures, and a sanitized-report limitation that
  prevents exact predicate/endpoint/evidence attribution. It recommends
  offline design of a two-step extractor; no f11 rerun or new preregistration
  is authorized by this task.
- [x] **S12-RM-19 — Owner review of the f12 two-step design proposal:** Approved
  the two-step direction with required pre-preregistration conditions. Stage 2
  receives runtime-only source context plus an authoritative server-owned
  candidate table; gold-/predicted-entity arms use separate paired calls, while
  gold-relations is a zero-provider integrity control. The review versions
  mutually exclusive semantic/evidence buckets, denominators and hard/semantic
  thresholds. It does not authorize preregistration or provider execution.
- [ ] **S12-RM-20 — Implement f12 offline contracts and diagnostic fixtures:**
  Version both stage envelopes, deterministic bucket matching/precedence,
  denominator reconciliation, gold-relations integrity control, gold- and
  predicted-entity oracle fixtures, sanitized report schema, paired schedule
  and zero-call guards. Freeze no execution package and issue no preregistration
  until a separate owner review accepts this offline evidence.

#### Phase F-S — Candidate Selection Resume Path

- [ ] **S12-78 — Select one candidate configuration:** Apply the registered
  multi-metric rule to the G5-R evidence without inspecting held-out data.
- [ ] **S12-79 — Evaluate the candidate on validation:** Run once after selection
  across atomic extraction, longitudinal graph state, and grounded competency
  answers; preserve the complete result, including regressions.
- [ ] **S12-80 — Run hard-invariant regression:** Reject any candidate that
  weakens safety, provenance, isolation, review, or fail-explicit behavior.
- [ ] **S12-81 — Freeze candidate artifacts:** Bind code, prompt, model,
  ontology, tools, dataset v3, configuration, evaluator, and result digests.
- [x] **S12-82 — Prepare the draft G5 packet:** Compare baseline and candidate by
  slice, confidence interval, business metric, latency, and cost.
- [x] **S12-83 — Approve G5 optimization freeze with limitations:** Human records
  that development experiments may proceed, while candidate validation, freeze
  and held-out evaluation remain locked behind candidate hard invariants.

### Phase G — Held-out Business Evaluation and G6

- [x] **S12-84 — Prepare held-out run preregistration:** Record candidate,
  evaluator, metrics, thresholds, reviewer protocol, and abort conditions. The
  existing artifact is a historical draft and does not authorize a v3 run.
- [ ] **S12-R24 — Version the G6 preregistration:** After S12-81, bind dataset v3,
  the frozen candidate, evaluator, business metrics, reviewer protocol, abort
  conditions, and custody procedure without inspecting held-out payload or gold.
- [ ] **S12-85 — Verify test custody and digests:** Human confirms the sealed
  bundle matches the approved G3.1 dataset lineage and has not been exposed.
- [ ] **S12-86 — Execute the blinded test run:** Evaluate the frozen candidate
  once and preserve all passing and failing slice results.
- [ ] **S12-87 — Conduct target-role review:** At least three qualified reviewers
  assess at least 12 blinded scenarios independently.
- [ ] **S12-88 — Measure the manual baseline:** Use a randomized,
  counterbalanced protocol for the same reviewers to structure and answer
  matched business material without Projecta assistance.
- [ ] **S12-89 — Compare business utility:** Compute acceptance, correction,
  review-time, usefulness, trust, and manual-baseline differences.
- [ ] **S12-90 — Review ontology gaps:** Classify every held-out semantic gap and
  invoke governed ontology evolution only when competency questions require it.
- [ ] **S12-91 — Verify held-out evidence integrity:** Recompute bundle, run,
  result, and reviewer-record digests and reject tampering or omission.
- [x] **S12-92 — Prepare the draft G6 packet:** Bind held-out semantic, business,
  operational, reviewer, gap, and residual-risk evidence.
- [ ] **S12-93 — Approve G6 business quality:** Human business and semantic
  reviewers approve the bounded claim, reject it, or require a new benchmark
  version; failed metrics remain visible.

### Phase H — Reproducibility and G7 Closure

- [ ] **S12-94 — Publish the dataset card:** Document intended use, composition,
  origin, annotation, splits, known bias, privacy, licensing, and limitations.
- [ ] **S12-95 — Publish the evaluation card:** Document model/prompt/tool
  configuration, metrics, results, uncertainty, cost, and non-generalization.
- [ ] **S12-96 — Publish the error backlog:** Prioritize observed data,
  ontology, prompt, agent, tool, model, UX, and runtime improvements.
- [ ] **S12-97 — Update product claims:** Align README, roadmap, and release
  language with only the evidence approved at G6.
- [ ] **S12-98 — Run the full regression gate:** Preserve existing API, web,
  Semantic Core, ontology, connector, Compose, and release-contract behavior.
- [ ] **S12-99 — Prepare the G7 packet:** Bind reproducibility evidence,
  approved claims, residual risks, backlog, and release recommendation.
- [ ] **S12-100 — Approve G7 closure:** Human closes Sprint 12 and decides
  whether to release, continue quality optimization, or resume deferred M7
  capability breadth.

## Acceptance Matrix

| Boundary | Sprint 12 acceptance |
| --- | --- |
| Business coverage | Every G0 journey has atomic and longitudinal evidence plus expected reviewer and question outcomes. |
| Dataset trust | Every case has origin, permission, sensitivity, version, split, and digest; normalized-template leakage, inconsistent language metadata, repeated scenario lineage across splits, or contradictory scenario gold blocks G3.1. |
| Annotation | G2 agreement passes; validation/test disagreements are independently adjudicated. |
| Ontology | Every gold concept maps to released semantics or an explicit governed gap; no force-fit or agent-approved ontology release. |
| Extraction | Slice-level entity, semantic relation, relation evidence, link, entity span, abstention, and hallucination metrics are reported separately and meet G6 thresholds. |
| Graph and retrieval | Longitudinal checkpoints and competency-question answers meet correctness, citation, completeness, and freshness thresholds. |
| Human value | Target-role blind review meets acceptance, correction, time, usefulness, and trust thresholds against the manual baseline. |
| Safety | Isolation, provenance, SHACL, allowlist, no-direct-assertion, and fail-explicit invariants remain 100%. |
| Reproducibility | Dataset, code, ontology, prompt, model, tool, configuration, evaluator, and results are versioned and digest-bound. |

## Definition of Done

- G0 through G7 have explicit human decisions bound to exact evidence.
- The development/validation benchmark is repository-local, sanitized,
  versioned, documented, lineage-disjoint, semantically consistent, and
  executable without access to the held-out gold.
- The held-out run is performed only after G5 candidate freeze and is never
  silently repeated or selectively reported.
- Baseline and candidate results report every required slice, including zero,
  failed, abstained, and missing outputs.
- All hard invariants pass; any waiver is a rejected Sprint 12 business-quality
  claim rather than a relabeled success.
- The final packet distinguishes benchmark evidence from tenant, provider,
  language, and production-scale generalization.
- The next sprint is selected from measured errors and approved business value,
  not from unvalidated capability breadth.

## Non-Goals and Guardrails

- Do not add a new connector, webhook, continuous synchronization, outbound
  action, generic agent platform, or tenant-administration surface in Sprint 12.
- Do not train or fine-tune a model unless a separate data-rights, security,
  cost, and reproducibility decision is explicitly approved.
- Do not put customer, work-tenant, personal, secret, or unapproved production
  data in Git, prompts, artifacts, logs, or external model calls.
- Do not let the model that drafts a case be the sole annotator or adjudicator.
- Do not optimize against validation repeatedly or expose test inputs/gold to
  agents before G6.
- Do not change ontology terms, SHACL shapes, inference rules, or release
  versions outside `$projecta-evolve-ontology` and human semantic approval.
- Do not collapse semantic, business, safety, latency, and cost into one score.
- Do not claim tenant readiness solely from synthetic data, pooled F1, or a
  single reviewer.

## Notes / Blockers

- Qualified Vietnamese, English, and Japanese annotator availability is a G1
  feasibility constraint. Unsupported language slices must be removed
  explicitly rather than weakly labeled.
- Authorized tenant-like data is not assumed. If no permitted pilot data is
  available, the sprint may approve only a synthetic/de-identified benchmark
  claim and must retain the external-validity limitation.
- The initial numerical thresholds are pre-registration defaults, not evidence
  that the current product already meets them.
- Dataset work may expose ontology gaps. Such gaps are findings, not permission
  to change the ontology or redefine operational state as RDF domain truth.
