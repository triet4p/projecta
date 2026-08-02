# Task Summary: S5-08 — Record the provider decision

**Sprint:** Sprint 5
**Task:** S5-08

## Summary of Work

Selected the OpenAI-compatible Responses API shape through the configurable
DeepSeek endpoint as the first live adapter and recorded the provider-neutral
gateway constraint, required model configuration, requested credential
boundary, bounded resilience configuration, canonical replay CI rule, and
replacement conditions.

## Files Modified

- `.agents/memory/decisions.md` — append-only architectural decision.
- `docs/architecture/llm-provider-decision.md` — operational decision record.

## Testing

- **Status:** `git diff --check` passed; no provider SDK or network call was added by this decision task.
- **Execution Command:** `git -c safe.directory=F:/ai-ml/projecta diff --check`

## Governance Note

The technology gate was bypassed under the user's Sprint 5 instruction. The
decision is recorded, but live credentials remain opt-in and no production
data submission is authorized.
