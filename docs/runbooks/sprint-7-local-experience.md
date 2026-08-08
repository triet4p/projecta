# Sprint 7 local experience runbook

This runbook starts the canonical local Compose experience. The browser talks
to the web container, which reverse-proxies only the public Application API and
health routes. The browser never receives the trusted context secret or raw LLM
credential.

## Prerequisites

- Docker Desktop with Compose v2.
- `uv` and Node.js 22 for source-level checks.
- A deployment-owned trusted context secret and Fernet master key. Generate a
  local master key with:

  ```text
  uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

- Set the deployment-owned trusted context secret and Fernet master key. No
  `PROJECTA_LLM_*` values are required for the first start in experience mode;
  the Settings screen creates the active provider profile after the app opens.
  Optional `PROJECTA_LLM_*` values remain available for headless/replay
  bootstrap and fail closed when incomplete; never commit these values.

## Start and first run

Set the required variables in the process environment, then run:

```text
docker compose -f compose.yaml -f compose.dev.yaml --profile web up --build
```

Open `http://localhost:3000`. The experience adapter supplies the fixed local
project and actor context. Open Settings, enter the provider URL/model and
credential, save, and confirm that the credential field is empty after the
write. Use Test connection before extraction when the provider is reachable.

The supported workflow is Quick Note extraction or typed capture, candidate
validation, Requirement confirmation or rejection, current knowledge/history/
evidence inspection, and bounded natural-language Q&A. Arbitrary SPARQL,
project/actor overrides, graph IRIs, and provider payloads are not UI features.

## Rotation, removal, and recovery

- Enter a replacement credential and choose **Rotate credential**. The active
  profile revision changes and the prior encrypted record is deleted.
- Choose **Remove** to deactivate the profile and delete its secret reference.
  Extraction then fails closed until Settings is configured again.
- If the encrypted store is unavailable or the master key is wrong, restore the
  deployment-owned master key or recover the operational volume from backup;
  the API does not return plaintext or silently fall back to browser state.
- To reset a disposable local environment, use a unique Compose project and
  `docker compose ... down --volumes --remove-orphans`. This removes the local
  operational volume and is not a production recovery procedure.

## Production boundary

The experience mode is for the local Compose profile. Production deployments
must set `PROJECTA_API_RUNTIME_MODE=production`, use immutable API/web images,
and provide an approved trusted-context/authentication boundary. The browser
must not be given deployment secrets.
