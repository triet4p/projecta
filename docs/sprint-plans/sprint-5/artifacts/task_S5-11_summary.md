# Task Summary: S5-11 — Create the versioned evaluation dataset

**Sprint:** Sprint 5
**Task:** S5-11

## Summary of Work

Added synthetic dataset `s5.v1` with representative entity, relation, bounded
link, Unicode evidence, ambiguity, empty, adversarial prompt-injection, and
cross-project-negative slices. Gold annotations use the exact source text and
Unicode-code-point offsets; empty/abstention is explicit and no production or
sensitive data is included.

## Files Modified

- `evaluation/sprint-5/README.md`
- `evaluation/sprint-5/dataset.v1.json`

## Testing

- **Status:** JSON artifact added; structural runner validation is assigned to S5-27.
- **Manual check:** dataset is versioned, read-only by contract, synthetic, and contains no credentials or production payloads.
