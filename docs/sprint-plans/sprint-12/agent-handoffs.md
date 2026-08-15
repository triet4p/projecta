# Sprint 12 Remaining-Agent Handoffs

**Status:** `READY_FOR_DELEGATION`

This document splits the remaining Sprint 12 work into bounded assignments for
smaller agents. Each assignment must preserve the owner-delegated AI annotation
claim boundary and must not mark a task complete from a prepared contract or a
missing-output report.

## Shared prerequisites

Before starting any assignment:

1. Read `AGENTS.md`, `.agents/memory/decisions.md`, `docs/PLAN.md` and
   `docs/sprint-plans/sprint-12.md`.
2. Read the gate packet and task summaries named by the assignment.
3. Preserve `humanEvidence: false` for agent-produced annotation artifacts.
4. Never commit API keys, runtime secrets, raw tenant payload, held-out inputs,
   held-out gold or unsanitized reviewer text.
5. Use `$implement-atomic-task`; update the task summary and sprint checkbox
   only after executable evidence passes.
6. Run the assignment tests plus `git diff --check` before handoff.

## Handoff A — Runtime-backed v0.6.0 baseline

**Tasks:** S12-68 and S12-69.

**Inputs:**

- `scripts/sprint12_evaluator.py`
- `evaluation/sprint-12/baseline/baseline-report.v1.json`
- released `v0.6.0` prompt/runtime contracts
- the owner-provided runtime environment:
  `PROJECTA_LLM_TYPE`, `PROJECTA_LLM_BASE_URL`, `PROJECTA_LLM_API_KEY`, and
  `PROJECTA_LLM_MODEL`

**Important:** The current evaluator only detects those variables. Even when
they are present, `build_baseline_report()` returns
`NOT_EXECUTED_ADAPTER_NOT_CONFIGURED`; the agent must implement a real bounded
adapter/run path rather than changing the status string.

**Work:**

1. Load only development and validation cases through the versioned loader.
2. Execute the unchanged `v0.6.0` extraction configuration with bounded output,
   one recorded attempt and no hidden retry.
3. Persist sanitized predictions and operational records keyed by case ID; do
   not persist source text or credentials in the evidence report.
4. Score every case, including failures and missing outputs.
5. Populate hard invariants, slice metrics, latency, usage and configured cost.
6. Classify each observed failure with the finite error taxonomy.
7. Regenerate the JSON/Markdown baseline evidence and update G4.

**Done when:** baseline status is runtime-backed, 160 case IDs are accounted
for, missing outputs remain visible, configuration/model/prompt/manifest/code
digests are bound, S12-68/69 summaries are updated, and Phase E tests pass.

**Commands:**

```text
uv run --script scripts/sprint12_evaluator.py
uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_e_contract.py
uv run --project apps/api ruff check scripts/sprint12_evaluator.py scripts/tests/test_sprint12_phase_e_contract.py
git diff --check
```

## Handoff B — Controlled optimization and candidate freeze

**Tasks:** S12-73 through S12-81. Start only after Handoff A produces a scored
runtime baseline.

**Inputs:**

- `scripts/sprint12_optimization.py`
- `evaluation/sprint-12/optimization/experiment-registry.v1.json`
- the runtime-backed baseline report

**Work:**

1. Execute the five registered development-only dimensions separately:
   prompt, context, agent workflow, tool and model.
2. Change exactly one declared dimension per experiment and retain all governed
   artifact digests.
3. Record all runs, regressions, failures, latency and cost; do not silently
   discard a losing experiment.
4. Apply the registered multi-metric selection rule once.
5. Evaluate the selected candidate on validation once.
6. Run all hard-invariant regressions.
7. Freeze code, prompt, model, ontology, tools, configuration, evaluator and
   result digests only if the candidate is selected and invariants pass.

**Done when:** one candidate is `FROZEN`, or the packet truthfully records
`NO_SELECTION`; S12-73…81 match executed evidence and Phase F tests pass.

**Commands:**

```text
uv run --script scripts/sprint12_optimization.py
uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_f_contract.py
uv run --project apps/api ruff check scripts/sprint12_optimization.py scripts/tests/test_sprint12_phase_f_contract.py
git diff --check
```

## Handoff C — External held-out custody

**Tasks:** S12-55 and S12-85.

**Owner:** A custodian operating outside the agent-visible repository. A normal
repository agent cannot complete this assignment alone.

The current test metadata is a deterministic preparation fixture and is
explicitly `reconstructibleFromRepository: true`; it is ineligible for held-out
use. Do not relabel or encrypt that reconstructed material and call it sealed.

**Work:**

1. Author a new 40-atomic/6-scenario bundle outside the repository without using
   repository-visible generation templates.
2. Run privacy, license, provenance and semantic review in the custody
   environment.
3. Seal inputs and gold separately with access logging and named custodian.
4. Publish only schema versions, counts, per-item opaque IDs/digests and bundle
   digest to the repository.
5. Set `reconstructibleFromRepository: false`, `eligibleForHeldOut: true` and
   `payloadPresent: true` only when the external custody boundary actually holds
   the matching payload.
6. Run custody verification without opening the bundle to the implementation
   agent.

**Done when:** `verify_test_custody()` returns `CUSTODY_VERIFIED`, the external
custodian signs the exact bundle digest, and no payload/gold enters Git or agent
logs.

## Handoff D — Blinded run and business review

**Tasks:** S12-86 through S12-91 and S12-93. Start only after a frozen candidate
and verified custody both exist.

**Work:**

1. Bind the preregistration to exact candidate, evaluator, metric and bundle
   digests before opening the test bundle.
2. Execute one blinded run and preserve every result.
3. Collect sanitized records from at least three qualified target-role
   reviewers over at least 12 blinded scenarios.
4. Run the randomized, counterbalanced manual baseline with the same reviewers.
5. Compute business utility and inspect every ontology gap without changing the
   production ontology in this assignment.
6. Recompute evidence digests and reject omission, tampering or reviewer
   independence violations.
7. Request G6 approval for a bounded claim only if all pre-registered thresholds
   and hard invariants pass.

**Done when:** the G6 packet contains real blinded, reviewer, manual-baseline,
utility and integrity evidence. Agent-only review cannot be presented as
target-role human utility.

**Commands:**

```text
uv run --script scripts/sprint12_heldout.py
uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_g_contract.py
uv run --project apps/api ruff check scripts/sprint12_heldout.py scripts/tests/test_sprint12_phase_g_contract.py
git diff --check
```

## Handoff E — G7 closure artifacts

**Tasks:** S12-94 through S12-100. Start only after the G6 decision exists.

**Work:**

1. Publish dataset and evaluation cards with composition, provenance, results,
   bias, uncertainty and non-generalization limits.
2. Produce an error backlog grouped by data, annotation, ontology, prompt,
   context, agent, tool, model, UX and runtime causes.
3. Update product claims to exactly the G6-approved boundary.
4. Run the full API, web, Semantic Core, ontology, connector, Compose and release
   regression gate.
5. Bind the G7 closure packet to exact artifacts and record the owner's release,
   continue-optimization or resume-M7 decision.

**Done when:** S12-94…100 have executable evidence, the sprint claim contains no
synthetic-to-tenant generalization, and G7 has an explicit owner decision.
