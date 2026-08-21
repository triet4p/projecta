# S12-R14 — v3 scale track

Status: complete

R14 expands only the patterns approved by R13 into an additive scale track:
208 atomic cases across 26 unique scenario lineages and 26 longitudinal
scenarios. The visible split is 160 development / 48 validation; test count is
zero and no held-out payload was created. Every lineage stays in one split.

The scale track has 52 relation-positive cases, 156 relation-negative cases,
26 explicit abstention cases, 87 Vietnamese, 41 English, 26 Japanese and 54
code-switched notes. It preserves approved entity/relation patterns, adds
domain-specific lexical variation, hard unresolved-choice negatives, exact
Unicode spans, chronology, contradiction checkpoints and bounded competency
answers. Offline checks show zero span errors, zero visible split leakage,
zero repeated scenario lineages, and no generator markers or sequence filler.

Changed artifacts:

- `scripts/generate_sprint12_v3_scale.py`
- `scripts/tests/test_sprint12_v3_scale.py`
- `evaluation/sprint-12/corpus/v3-scale/atomic-scale.v1.json`
- `evaluation/sprint-12/corpus/v3-scale/manifest-scale.v1.json`
- `evaluation/sprint-12/corpus/v3-scale/scenario-scale.v1.json`
- `evaluation/sprint-12/corpus/v3-scale/scenario-manifest-scale.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: span, language, leakage and scenario-consistency checks, scale
contract tests, Ruff, and `git diff --check`. R15 freeze remains pending; no
provider execution or held-out access was used.
