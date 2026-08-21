# S12-R11 — v3 pilot annotation and adjudication

Status: complete

S12-R11 publishes an owner-delegated AI adjudication packet for the 48 atomic
cases and six longitudinal scenarios in the v3 deep pilot. The packet binds
the source dataset and manifests by file/content digest, records the guide and
schema versions applied, and stores per-case rule IDs plus per-scenario review
decisions without duplicating raw source text.

The packet verifies code-point span integrity, released entity types and
predicates, labeled relation endpoints, relation evidence, explicit
abstention reasons, semantic-gap rationales, and scenario source-manifest
bindings. Coverage is explicit: 32 development / 16 validation cases, 15
relation-positive cases, 15 relations, six required abstentions, all four
declared languages, and seven represented entity types. There are no material
disputes, no independent human review claim, and `humanEvidence` remains false.

Changed artifacts:

- `scripts/adjudicate_sprint12_v3_pilot.py`
- `scripts/tests/test_sprint12_v3_pilot_adjudication.py`
- `evaluation/sprint-12/corpus/v3/gold-adjudication.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: adjudication packet integrity and tamper fixtures, full
`scripts/tests` suite, Ruff, and `git diff --check`. R12 quality gating remains
pending; no provider execution or held-out access was used.
