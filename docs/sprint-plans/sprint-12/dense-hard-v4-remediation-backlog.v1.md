# Dense-hard v4 remediation and strategy-redesign backlog

Status: `OFFLINE_ONLY_NEW_AUTHORITY_REQUIRED`.

This is a finite diagnostic backlog created after the immutable v4 failure. It
does not authorize a new candidate, provider call, human/external/held-out
run, production change, selection, promotion, or release.

1. **R1 — Occurrence coverage:** Define a source-only output strategy that
   preserves every repeated occurrence and binds relation endpoints to the
   correct occurrence without type-dependent identity.
2. **R2 — Relation grounding:** Add deterministic endpoint/trigger/evidence
   checks and a residual taxonomy for unsupported predicates, stale statements,
   and cross-sentence endpoint drift.
3. **R3 — Proposition routing:** Separate safe propositions, non-propositional
   distractors, and explicit unsafe propositions before finalization; require
   proposition-level quarantine receipts.
4. **R4 — Utility/safety routing:** Prevent over-abstention on expected-none
   utility cases while retaining exact full/partial safety behavior.
5. **R5 — Candidate contract tests:** Add mutation tests for type mismatch,
   occurrence duplication, relation endpoint swap, punctuation normalization,
   quarantine over/under-count, and unsupported finalization.
6. **R6 — Fresh benchmark design:** After new owner authority, author a fresh
   packet with no v1–v4 ID, raw text, normalized sentence, or digest reuse and
   preregister utility/safety denominators before any candidate exists.
7. **R7 — Independent evaluation gate:** Recompute per-item, slice, tier,
   correction, abstention, quarantine, and zero-unsafe metrics; require both
   strata and preserve the v1–v4 non-pooled comparison.

Exit criteria: all seven items have reviewable offline artifacts, the fresh
packet passes lineage checks, and a separate owner decision authorizes any
future candidate/evaluation. The v5 easy baseline remains historical only.
