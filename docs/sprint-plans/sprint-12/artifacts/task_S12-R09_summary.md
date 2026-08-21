# S12-R09 — Atomic v3 deep pilot authoring

Status: complete

S12-R09 authors a new `s12.corpus.atomic.v3.deep-pilot` fixture with 48
repository-visible cases across six distinct business storylines. Four
lineages are development (32 cases) and two are validation (16 cases); no
lineage crosses the split. The pilot includes 15 relation-positive cases,
explicit abstentions, questions, decisions, risks, progress claims,
requirements, constraints, multilingual notes, code-switching, typos,
follow-ups and unresolved decisions.

The Quick Notes contain no `Evidence marker`, distinguishing phrase, sequence
filler, or ID-only paraphrase. Each case binds synthetic origin, sensitivity,
license, permission reference, language, content digest, exact code-point
spans, and versioned case digest. Test payload count is zero and v1/v2 remain
unchanged. The dataset is authored but intentionally remains pending R10–R13
scenario, adjudication and quality gates.

Changed artifacts:

- `scripts/generate_sprint12_atomic_v3_deep_pilot.py`
- `scripts/tests/test_sprint12_atomic_v3_deep_pilot.py`
- `evaluation/sprint-12/corpus/v3/atomic-deep-pilot.v1.json`
- `evaluation/sprint-12/corpus/v3/manifest.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: pilot integrity and leakage fixtures, full `scripts/tests` suite,
Ruff, and `git diff --check`. No provider execution or held-out access was
used.
