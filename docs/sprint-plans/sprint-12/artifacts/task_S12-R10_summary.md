# S12-R10 — Longitudinal v3 deep pilot

Status: complete

S12-R10 authors six unique longitudinal episodes in
`s12.corpus.scenario.v3.deep-pilot`. Each episode has eight ordered events from
one atomic lineage, with explicit actors and chronology encoded in the review
rationales, create/update transitions, contradiction events, review decisions,
four graph checkpoints, and two competency-answer fixtures.

Four episodes are development lineages (J1–J4) and two are validation lineages
(J5–J6). No lineage crosses the split, no source sequence is reused with a
different gold interpretation, and no test payload is present. The scenarios
cover payments reconciliation, warehouse dispatch, identity migration, claims
automation, clinic scheduling, and field service. Each episode includes an
answerable current question and an ambiguous question requiring abstention.

Changed artifacts:

- `scripts/generate_sprint12_scenario_v3_deep_pilot.py`
- `scripts/tests/test_sprint12_scenario_v3_deep_pilot.py`
- `evaluation/sprint-12/corpus/v3/scenario-deep-pilot.v1.json`
- `evaluation/sprint-12/corpus/v3/scenario-manifest.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: scenario shape and lineage tests, scenario consistency validator,
manifest digest checks, full `scripts/tests` suite, Ruff, and `git diff --check`.
The pilot remains authored synthetic data with `humanEvidence: false`; no
provider execution or held-out access was used.
