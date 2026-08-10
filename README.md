# Projecta

Projecta turns project notes into structured, traceable knowledge. Use it to
organize notes, review extracted candidates, explore project relationships,
and ask questions grounded in recorded evidence.

## What you can do

- Work in separate project workspaces without entering or remembering IDs.
- Create structured notes from ordered, typed note items.
- Import note suggestions with AI assistance, then edit them before saving.
- Review and correct candidates before explicitly confirming or rejecting them.
- Explore a bounded project graph and ask evidence-backed questions.

## Quick start

You need Docker Desktop and [`uv`](https://docs.astral.sh/uv/) on Windows.
From PowerShell in the repository root, run:

```powershell
$env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = (New-Guid).Guid
$env:PROJECTA_API_SECRET_STORE_MASTER_KEY = uv run --project apps/api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$env:PROJECTA_API_RUNTIME_MODE = "experience"
$env:PROJECTA_API_EXPERIENCE_ACTOR_ID = "local-operator"
$env:PROJECTA_API_EXPERIENCE_PROJECT_CATALOG = "project-alpha,project-beta"
$env:PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS = "project-alpha|Project Alpha;project-beta|Project Beta"
docker compose -f compose.yaml -f compose.dev.yaml --profile web up --build
```

When all services are healthy, open <http://localhost:3000>.

## First steps

1. Select **Project Alpha** or **Project Beta** on the **Projects** page.
2. Open **Notes**, create a note with one or more typed items, then save or
   commit it.
3. Open **Graph** to explore the project and **Review Queue** to validate
   extracted candidates.
4. Open **Settings** to configure an OpenAI-compatible provider if you want to
   use assisted import or extraction. Manual structured notes work without it.
5. Use **Diagnostics** when a service reports an error; request IDs are shown
   so failures can be matched with container logs.

Projecta does not silently choose another project, retry a failed action, or
turn an unavailable result into an empty success. Review the visible error and
retry only after resolving its cause.

## Stop or reset

Stop the app while keeping local data:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile web down
```

To also delete all local Projecta data and start clean, add
`--volumes --remove-orphans`. This cannot be undone.

## Troubleshooting

Check service state and recent logs:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile web ps
docker compose -f compose.yaml -f compose.dev.yaml --profile web logs --tail=200 web api semantic-core fuseki
```

For detailed health and recovery guidance, see the
[operations guide](docs/runbooks/sprint-8-operations.md).

## License

Licensed under the [Apache License 2.0](LICENSE).
