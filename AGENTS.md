# Repository Guidelines

## Sources of Truth

Projecta is documentation-first. Begin with `docs/initialization/README.md`, then read the initialization documents relevant to the task. Use this precedence when instructions conflict:

1. Current user instruction.
2. `AGENTS.md`.
3. `.agents/memory/decisions.md`.
4. `docs/initialization/`.
5. Applicable `.agents/rules/`.
6. Existing implementation.

Read `.agents/memory/decisions.md` before architecture or technology changes. Use `$log-decision` for an approved decision; do not rewrite prior entries. Before diagnosing a recurring bug, search `.agents/memory/lessons-learned.md` when it exists. Use `$log-lesson` after resolving a reusable bug or environment-specific issue.

## Project Structure

Current repository content is primarily:

- `docs/initialization/`: product, architecture, memory, ontology, stack, and delivery guidance.
- `.agents/rules/`: reusable contributor rules.
- `.agents/skills/`: Projecta-specific agent workflows.
- `.agents/memory/`: durable decisions and lessons.

The planned application layout is defined in `docs/initialization/06-Tech-Stack.md`. Do not add empty `apps/`, `services/`, `connectors/`, `ontology/`, or infrastructure scaffolding without a working vertical slice.

## Rules and Skills

Load the applicable source rather than duplicating it:

- Git and commits: `.agents/rules/git.md`
- Markdown: `.agents/rules/markdown.md`
- Python: `.agents/rules/python.md`
- Changelog: `.agents/rules/changelog.md`
- Subagent workflow: read and follow both
  `.agents/rules/subagent-workflow.md` and
  `~/.agents/rules/subagent-workflow.md`; both are mandatory synchronized
  requirements. If they differ, apply the stricter compatible interpretation
  and report the divergence to the primary owner.
- Ontology evolution: `$projecta-evolve-ontology`

For ontology work, the project skill and human review gate are mandatory.

## Build and Validation

No executable application or root build configuration exists yet. Use:

```text
rg --files docs .agents
git diff --check
```

Follow `docs/initialization/06-Tech-Stack.md` and `08-Deployment-Choice.md` when build and Compose artifacts are introduced. Never report an unconfigured command as passing.

## Testing and Review

Derive test scope from the changed layer and its initialization document. Ontology changes must follow the validation and review packet required by `$projecta-evolve-ontology`.

PRs should state intent, affected boundaries, validation evidence, and unresolved risks. Reference the applicable rules instead of restating them. Never commit secrets, credentials, sensitive payloads, or production data.

## Graphify
You should use graphify to understand codebase more effiency, instead of scan all codebase. See `$graphify` skills
