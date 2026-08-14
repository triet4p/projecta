# Sprint 12 Ontology Reuse and Gap Audit

**Status:** `HUMAN_APPROVED_PENDING_IMPLEMENTATION`

**Scope:** S12-26 dataset-contract concepts required to annotate and evaluate
the eight G0-approved journeys.

## Semantic outcome

No ontology vocabulary change is proposed for the G1 dataset contract. The
dataset labels are evaluation artifacts and must refer to released Projecta
semantics where a released meaning exists. Dataset IDs, split, language,
origin, sensitivity, permission, digest, correction class, reviewer score,
custody state, leakage status and metric fields remain operational/evaluation
metadata outside RDF domain truth.

## Reuse classification

| Dataset need | Outcome | Released basis / boundary |
| --- | --- | --- |
| Note and NoteItem source material | Reuse released semantics | Communication/source ontology and source/evidence shapes |
| Requirement, Decision, Question, Task, Risk, Assumption, Constraint, ProgressClaim, ResearchFinding | Reuse released M3 allowlist | `llm-extraction-v04.ttl`, extraction contract and candidate shapes |
| `implements`, `blocks`, `dependsOn`, `supports`, `answers`, `resolves`, `constrainedBy` | Reuse released predicates | M3 relation contract; endpoints remain bounded and project-scoped |
| Candidate/asserted/inferred/provenance states | Reuse released lifecycle | Candidate, evidence, provenance, temporal and isolation boundaries |
| Grounded answer facts/citations/freshness | Reuse released retrieval projection | M4 retrieval contract; output remains a bounded projection |
| Review disposition and correction severity | Keep evaluation/operational | The benchmark measures reviewer behavior; it does not add a generic Note status or new RDF lifecycle term |
| Dataset split, custody, permission, license, content digest and leakage flag | Keep operational/evaluation | These govern benchmark handling, not project domain truth |
| Ambiguity, unsupported concept and semantic gap | Keep annotation/evaluation metadata | A gap may trigger a future governed ontology proposal; it is not a new term now |
| Longitudinal event/checkpoint records | Keep scenario gold/evaluation data | They test existing lifecycle/provenance behavior and do not create a second semantic read model |

## Competency and commitment gates

The G0 competency questions CQ-01 through CQ-16 are answerable using released
source, candidate, asserted, inferred, provenance, temporal and retrieval
semantics. No new class/property is required to score them.

The semantic-commitment interview is **not applicable to a new term** because
this audit proposes no class, property, controlled individual, SHACL shape or
rule. Dataset-only fields are explicitly classified as operational, evidence,
retrieval or evaluation metadata. Force-fitting them into RDF would create
unapproved lifecycle, identity or temporal commitments.

## Alternatives considered

1. Add benchmark-shaped RDF classes/properties for `EvaluationCase`, `ReviewScore`,
   `CorrectionClass`, `DatasetSplit` and `CustodyState`. Rejected because these
   describe benchmark operations rather than Projecta project knowledge and
   would add vocabulary without a product competency question.
2. Store the benchmark as opaque JSON only. Rejected because released semantic
   labels, evidence, lifecycle and retrieval checkpoints need typed validation
   and exact mapping to existing contracts.
3. Add provider- or language-specific ontology terms. Rejected because the G1
   purpose is to test released semantics across sources, not to encode a
   connector or language implementation.

## Compatibility and risk

- No Turtle, SHACL, rule, migration, ontology version or runtime RDF artifact
  changes are made.
- Existing extraction, candidate, evidence, provenance, isolation and
  retrieval queries remain the source of truth for scoring.
- A held-out gold concept that cannot map to released semantics becomes an
  explicit gap and blocks silent claim inflation; it may reopen the governed
  ontology workflow after G6 evidence.
- Annotation labels must not be mistaken for asserted facts or loaded into the
  runtime ontology without a separate approved implementation.

## Human review actions requested

- [x] Approve reuse/no-change semantic outcome.
- [x] Approve classification of dataset fields as operational/evaluation data.
- [x] Approve that discovered semantic gaps reopen ontology governance rather
  than being force-fit.
- [x] Authorize the G1 dataset contract and annotation work.
