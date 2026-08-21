# S12-R13 — G3.1-B pilot quality approval

Status: complete

The G3.1-B approval packet reviews 12 representative atomic cases spanning
entity, relation, abstention and progress patterns, all six longitudinal
timelines, contradiction checkpoints, review rationales, normalized-template
clusters, and metric computability. The v2 metric contract is bound with
semantic relation identity separated from evidence support/exactness and with
per-case/per-slice denominators required.

Approval is intentionally scoped: S12-R14 may scale only the v3 patterns that
passed the pilot. This packet does not authorize a provider call, held-out
access, G5, ontology claims, or business-utility claims. The pilot remains
synthetic owner-delegated AI review with `humanEvidence: false`. Gaps for J7/J8,
the `resolves` predicate, and `Assumption`/`ResearchFinding` types are recorded
for scale-up rather than hidden by pooled coverage.

Changed artifacts:

- `scripts/approve_sprint12_g31_b_pilot.py`
- `scripts/tests/test_sprint12_g31_b_pilot_approval.py`
- `evaluation/sprint-12/gates/g3.1-b-pilot-approval.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: approval packet contract tests, full `scripts/tests` suite, Ruff,
and `git diff --check`. No provider execution or held-out access was used.
