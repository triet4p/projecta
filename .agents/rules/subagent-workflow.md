# Subagent Workflow Rules

## Scope and precedence

This rule records Projecta-specific delegation constraints and non-OMP guidance.
For OMP sprint work, `skill://omp-subagent-flows` is the canonical workflow;
implementation workers also follow `skill://implement-atomic-task`. This file is
not a synchronized copy of a global workflow: OMP role/model routing,
concurrency, asynchronous jobs, evidence gates, and exact-snapshot checkpoint
ownership come from the canonical skill and effective role definitions.
Outside OMP, follow the coding agent's native lifecycle; never translate OMP
agent names, tools, lifecycle operations, or artifact URLs into another runtime.

Apply requirements in this order:

1. System, developer, tool, skill, and safety requirements.
2. Explicit user instructions.
3. `AGENTS.md`, approved decisions, and applicable repository documentation.
4. Projecta-specific requirements in this rule; for OMP workflow mechanics, follow
   the canonical OMP skill and effective role definitions.

The primary owner is the agent responsible for the user-facing task. A
subagent is an owner-delegated worker, not an independent task owner.

## When to delegate

Outside OMP, use this project-local delegation heuristic. In OMP, worker
selection and assignment follow `skill://omp-subagent-flows`.

Use exactly one subagent when delegation materially improves accuracy or
keeps technical context focused, especially when any of these conditions apply:

- The task is complex, multi-step, or has several dependent validation gates.
- The codebase or relevant subsystem is large, unfamiliar, or difficult to
  understand safely in the primary owner's remaining context.
- The work crosses layers, packages, services, languages, or architectural
  boundaries.
- Substantial code, documentation, configuration, history, or artifact reading
  is required.
- Commands, tests, execution, diagnosis, investigation, reproduction, or
  verification are required.
- Validation is long-running or benefits from an independent focused audit.
- The current subagent or primary-owner context is polluted, stale, or too broad
  for a reliable focused pass.

Keep work with the primary owner when it is a direct user question, a simple
owner decision, a tiny prose edit, a clearly bounded one-file change, or work
that can be completed and verified immediately without substantial technical
investigation.

Do not delegate merely to parallelize trivial work, avoid a straightforward
owner decision, or obtain an unscoped second opinion.

## Non-OMP agent concurrency and model selection

Outside OMP, at most one subagent may be active at a time. Do not spawn a
replacement until the current subagent has completed, been intentionally
stopped, or returned a definitive blocker.

For OMP, agent limits, role/model routing, and attempt freshness are determined
by `skill://omp-subagent-flows` and effective role definitions; this file sets
no OMP-wide model or reasoning-effort pin.

Outside OMP, reuse the same subagent for follow-up work, clarification, and
post-fix auditing unless its context is polluted, stale, or otherwise unusable.
Replacement for convenience or speculative parallelism is not allowed.

A subagent must not spawn descendants or delegate its assigned work further.

## Delegation contract

Outside OMP, use this delegation contract. OMP assignment, write authority,
worker evidence, and handoff boundaries follow the canonical workflow.

Before delegation, the primary owner defines the objective, scope, relevant
files or boundaries, constraints, expected evidence, authorization boundary,
and completion criteria.

Delegate technical groundwork such as:

- Reading code, documentation, architecture, configuration, history, or
  governed artifacts.
- Running explicitly scoped commands, tests, linters, builds, or checks.
- Investigating failures, regressions, dependencies, edge cases, or behavior.
- Verifying a proposed fix, contract, invariant, report, or validation result.

Subagent work is read-only by default. The primary owner must explicitly
delegate any edit, generated artifact, or other write. Even when edits are
delegated, the primary owner retains responsibility for reviewing the result,
deciding the final form, and approving the final change.

The subagent returns evidence, commands run, relevant findings, unresolved
risks, and a clear completion or blocker status. It must not claim owner
authorization, approval, completion of the overall task, or correctness beyond
the evidence it actually obtained.

## Owner responsibilities

Outside OMP, the following owner-workflow rules apply. In OMP, Main's
responsibilities are defined by `skill://omp-subagent-flows`.

The primary owner sets the plan and scope, resolves conflicts, synthesizes the
findings, chooses the final approach, performs or approves final edits, checks
authorization, coordinates follow-up work, and owns the user-facing result.

Subagent recommendations are advisory. The primary owner independently decides
whether the result satisfies the user request, applicable rules, validation
requirements, and authorization boundary.

## Project-wide authorization and confidentiality

These safeguards apply to Projecta work in every agent environment.

Destructive operations, external communications, provider or API calls,
credential use, deployments, releases, and other externally consequential
actions remain owner-authorized. Delegating a command does not grant that
authority.

Never expose secrets, credentials, tokens, private payloads, or production data
in delegation prompts, outputs, logs, or reports.

## Non-OMP follow-up, audit, and completion

These lifecycle rules apply outside OMP. For OMP corrections, reviews,
completion, and checkpoints, follow the canonical workflow and effective roles.

After the subagent reports, the primary owner reviews the evidence, synthesizes
the result, and performs or approves the final edits. After any owner-applied
fix arising from delegated work, call the same usable subagent back for a
post-fix audit. If that subagent's context is polluted, stale, or unusable,
record the reason and use a replacement only after the prior subagent is no
longer active.

Only finish, end, or retire the subagent after its assigned work is complete,
required validation has passed or any limitation is explicitly recorded, all
unresolved risks are reported, and the relevant authorization is valid. A
subagent completion response does not by itself authorize or complete the
broader owner task.

If the assigned work or authorization remains incomplete, continue with the
same subagent when possible or report the blocker. Create a replacement only
after the prior subagent is no longer active and its context is demonstrably
polluted, stale, or unusable.
