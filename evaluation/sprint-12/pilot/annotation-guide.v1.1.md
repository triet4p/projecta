# Sprint 12 Annotation Guide v1.1 — Pilot Revision

**Status:** `G2_APPROVED_WITH_LIMITATIONS`

This revision is limited to two ambiguity rules exposed by the synthetic
calibration fixture. It does not change the released ontology, types,
predicates, thresholds or split policy.

## Rule AG-01 — Research finding versus progress claim

An explicit result marker such as “Kết quả” is not sufficient by itself to
prove a ResearchFinding in every context. Use `ResearchFinding` when the source
attributes a result to a research activity or source-backed investigation. Use
`ProgressClaim` when it reports project work or status. If the context cannot
resolve the distinction, annotate the ambiguity and abstain rather than
guessing.

## Rule AG-02 — Vague future language

Phrases equivalent to “maybe review later” without a concrete object, actor,
question or commitment are not `Question` or `Task`. They require abstention
for insufficient specificity.

## Revision control

The two rules are versioned from `annotation-guide.v1` and must be re-tested on
a fresh calibration subset. The synthetic fixture report is diagnostic only:
its span score is recomputed from the bound labels, while scenario and
question-answer agreement are not evaluated because no independent labels
exist. A qualified human annotation pilot is still required before any claim
of qualified annotator reliability or production-scale readiness.
