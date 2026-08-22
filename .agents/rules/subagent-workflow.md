# Subagent Workflow Rules

## Scope and precedence

This workflow is mandatory whenever the primary owner considers delegating
work to a subagent.

The repository copy and `~/.agents/rules/subagent-workflow.md` are synchronized
requirements. Read and follow both when they exist. Repository-specific
constraints remain binding; the global copy supplies shared defaults and must
not weaken repository requirements. If the copies differ, apply the stricter
compatible requirement, report the divergence to the primary owner, and do not
silently choose the weaker interpretation.

Apply requirements in this order:

1. System, developer, tool, skill, and safety requirements.
2. Explicit user instructions.
3. `AGENTS.md`, approved decisions, and applicable repository documentation.
4. Both copies of this rule, using the stricter compatible interpretation if
   they differ.

The primary owner is the agent responsible for the user-facing task. A
subagent is an owner-delegated worker, not an independent task owner.

## When to delegate

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

## Active-agent limit and model

At most one subagent may be active at a time. Do not spawn a replacement until
the current subagent has completed, has been intentionally stopped, or has
returned a definitive blocker.

Whenever a subagent is used, use exactly `gpt-5.6-luna` with reasoning effort
`high`. Do not silently substitute another model or effort level. If this
configuration is unavailable, report the blocker to the user or primary owner.

Reuse the same subagent for follow-up work, clarification, and post-fix auditing
unless its context is polluted, stale, or otherwise unusable. Replacement for
convenience or speculative parallelism is not allowed.

A subagent must not spawn descendants or delegate its assigned work further.

## Delegation contract

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

The primary owner sets the plan and scope, resolves conflicts, synthesizes the
findings, chooses the final approach, performs or approves final edits, checks
authorization, coordinates follow-up work, and owns the user-facing result.

Subagent recommendations are advisory. The primary owner independently decides
whether the result satisfies the user request, applicable rules, validation
requirements, and authorization boundary.

Destructive operations, external communications, provider or API calls,
credential use, deployments, releases, and other externally consequential
actions remain owner-authorized. Delegating a command does not grant that
authority.

Never expose secrets, credentials, tokens, private payloads, or production data
in delegation prompts, outputs, logs, or reports.

## Follow-up, audit, and completion

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
