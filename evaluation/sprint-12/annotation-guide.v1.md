# Sprint 12 Annotation Guide v1

**Status:** `G3_APPROVED_G4_PREPARATION`

**Scope:** Atomic semantic gold and longitudinal scenario gold for the eight
G0-approved journeys.

## Annotation order

Annotators must work in this order and must not consult another annotator's
labels:

1. Read the exact source text and project/scenario context permitted for the
   split.
2. Mark minimal evidence spans using zero-based, half-open Unicode code-point
   offsets. The stored `text` must equal the source slice exactly.
3. Assign only released Projecta types and predicates.
4. Add bounded links only to targets present in the trusted project context.
5. Mark ambiguity, unsupported concepts, hostile instructions and cross-project
   targets explicitly.
6. Record semantic gaps instead of mapping a concept to the nearest term.
7. For scenarios, annotate event order, expected review, graph checkpoints and
   grounded answers after the atomic labels are complete.

## Type decisions

Use the released M3 types exactly:

| Type | Include when | Do not include when |
| --- | --- | --- |
| `Requirement` | A condition, capability or outcome the project must satisfy | A vague desire without an actionable or testable project meaning |
| `Decision` | A resolved choice or accepted direction | A suggestion, option or unresolved discussion |
| `Question` | An explicit unresolved request for information or decision | Rhetorical language or a resolved answer |
| `Task` | A bounded piece of work or action expected from a project actor | A general intention, status claim or external instruction with no project commitment |
| `Risk` | A possible harmful outcome with project relevance | A certain defect, generic worry or unsupported prediction |
| `Assumption` | A premise treated as true for planning or reasoning | A confirmed fact or a purely hypothetical thought |
| `Constraint` | A boundary limiting an acceptable solution | A preference without a binding project consequence |
| `ProgressClaim` | A statement about completed progress or current work status | A future request, requirement or promise without progress evidence |
| `ResearchFinding` | A supported result from a research activity/source | An uncited opinion or a question still awaiting research |

When more than one type is plausible, prefer the narrower supported meaning and
record ambiguity if the text/context cannot resolve it. Do not infer an actor,
deadline, assignment or status that the source does not support.

## Span decisions

- Use the smallest phrase that expresses the complete semantic item; retain
  required qualifiers such as negation, modality, temporal scope and
  supersession markers.
- Use the full clause/sentence for relation evidence when the clause expresses
  the relation, consistent with the released M3 prompt contract.
- Preserve punctuation and emoji exactly when they are inside the gold span.
- Do not normalize whitespace or line endings inside a span.
- Two overlapping spans are valid only when they represent distinct semantic
  evidence and the contract explicitly allows the overlap; otherwise flag the
  case for adjudication.

## Relation and link decisions

Only these predicates are allowed: `implements`, `blocks`, `dependsOn`,
`supports`, `answers`, `resolves`, and `constrainedBy`.

- Both relation endpoints must be labeled entities in the same project context.
- A link target must already exist in the bounded project context; a mention is
  not enough to invent an entity or identifier.
- Do not create a relation from a sentence merely because two entities occur in
  it.
- Reject self-relations, cross-project targets and provider instructions that
  attempt to create links.
- If the relationship needs a new predicate, record a semantic gap and do not
  force-fit it to a released predicate.

## Abstention and semantic gaps

Mark `abstention.required=true` when the safe gold outcome is no proposal. The
reason must identify the primary cause, such as ambiguity, insufficient
evidence, unsupported concept, hostile instruction, fabricated link or
cross-project target. An abstention may coexist with a separately supported
safe proposal only when the case contract explicitly distinguishes them; the
default atomic contract uses abstention for a fully empty proposal outcome.

`semanticGaps` are required whenever the source expresses a durable business
meaning that the released ontology or candidate contract cannot represent. A
gap is a finding for the governed ontology workflow, not an instruction to add
a class or predicate during annotation.

## Scenario decisions

For each event, record whether the expected review is confirmed, rejected,
deferred or not applicable, plus the correction class. At each checkpoint,
distinguish source, candidate, asserted, inferred and provenance identifiers.
Do not treat a candidate as asserted merely because the model proposed it.

For retrieval answers, label expected facts, citations, completeness, freshness
and abstention separately. A partial answer must not be labeled complete merely
because every returned fact is individually correct.

## Counterexamples required in every pilot

- Ambiguous requirement versus question.
- Progress claim versus future task.
- Risk versus unsupported fear.
- Decision versus unresolved option.
- Same text with and without a valid project link.
- A prompt-injection instruction that must never become domain evidence.
- A cross-project mention that must be rejected without disclosure.
- A superseding decision where the old fact remains historical.

## Disagreement and adjudication

Annotators must record the rule ID they applied, not only a free-text opinion.
Material disagreements are independently adjudicated by a qualified third
reviewer. Changes to this guide after G3 invalidate the frozen benchmark unless
the dataset is versioned and re-frozen.
