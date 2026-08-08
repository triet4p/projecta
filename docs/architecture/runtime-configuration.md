# Runtime Configuration and LLM Settings Security Contract — Sprint 7

**Status:** IMPLEMENTATION_BASELINE — S7-07 and S7-14 approved
**Task:** S7-06

## Purpose

This contract separates deployment/bootstrap configuration from an authorized
interactive LLM profile. It defines what the web experience may read or write,
how credentials are handled, and how extraction resolves a configuration
snapshot. It is a security and application boundary. S7-14 selects
application-encrypted operational storage as the local/self-hosted baseline,
while keeping the secret-store port provider-neutral for a future
Vault-compatible migration.

The current `PROJECTA_LLM_TYPE`, `PROJECTA_LLM_BASE_URL`,
`PROJECTA_LLM_API_KEY`, and `PROJECTA_LLM_MODEL` environment contract remains
valid for headless, CI, replay, and deployment bootstrap. Interactive settings
must not edit `.env` or replace that adapter implicitly.

## Configuration Modes

| Mode | Source | Use | Failure behavior |
|---|---|---|---|
| `headless` | Environment adapter from `PROJECTA_LLM_*` | CI, replay, tests, and deployment bootstrap. | Missing/unsupported values fail closed for extraction; liveness may still report process health. |
| `experience` | Active server-side profile metadata plus approved SecretStore | Local web workflow and future authorized server workflows. | Missing/invalid profile or unavailable store fails closed; no silent environment fallback during an interactive operation. |
| `production` | Future deployment-owned provider profile/secret manager | Not implemented by Sprint 7. | Local fixed context and browser settings adapter are disabled. |

The application selects the mode from deployment composition, not from a
browser field. An extraction operation receives one immutable provider
configuration snapshot, including profile revision, before creating its
gateway. A settings change affects later operations without mixing credentials
inside a request already in progress.

## Profile Model

The persisted non-secret profile may contain:

| Field | Client visibility | Rule |
|---|---|---|
| Opaque profile ID | Redacted/opaque | Never an internal database key or secret locator. |
| Provider type | Yes | Current allowlist is exactly `openai-response` and `openai`. |
| Base URL | Policy-filtered | HTTPS required outside explicit local/test mode; reject credentials, fragments, and unsafe URL components. |
| Model ID | Yes | Non-empty, bounded, provider-neutral string; `replay:*` remains test/deployment behavior. |
| Active state | Yes | Only one active interactive profile for the experience scope. |
| Revision | Yes | Monotonic revision used for optimistic concurrency and gateway snapshots. |
| Credential configured | Yes | Boolean/status only; never key length, hash, prefix, or provider token. |
| Health/last checked time | Yes | Sanitized status and timestamp; no provider response body. |
| Created/updated/audit timestamps | Yes | Operational metadata only. |
| Secret reference | No | Opaque internal reference usable only by SecretStore; never serialized to the browser. |
| Raw credential | Never | Must not be persisted in profile metadata or returned anywhere. |

## Operations and Semantics

| Operation | Input | Result and safety rule |
|---|---|---|
| Read active profile | No secret input | Return provider type, policy-filtered URL, model, revision, active state, credential-configured status, and sanitized health. |
| Create/update profile | Provider metadata plus credential when needed | Validate all fields, write secret through SecretStore, then commit metadata. Failed writes retain the prior active profile and do not expose plaintext. |
| Rotate credential | Replacement credential plus expected profile revision | Store replacement, atomically move the profile to the new opaque reference, and clean up the old reference after successful commit. A conflict leaves the prior profile active. |
| Remove credential/profile | Expected profile revision and explicit confirmation | Delete or deactivate the active reference idempotently; active extraction becomes unavailable until a valid profile exists. No orphaned secret is intentional. |
| Test connection | Bounded provider/model request using a snapshot | Non-domain-mutating, timeout-bounded, sanitized outcome; never store response body or include the credential in telemetry. |
| Resolve for extraction | Operation/request context | Return immutable `{mode, profileRevision, providerType, baseUrl, model, secretHandle}` to server-side gateway composition only. |

The exact HTTP paths, request schemas, authorization seam, and concurrency
header are S7-08 work. The security semantics above are normative for that
contract.

## Secret-store baseline after S7-14

The experience profile resolves credentials through a provider-neutral
`SecretStore` port using opaque references. S7-14 does not add cryptographic
code or persistence: master-key custody/bootstrap, encrypted records,
recovery, rotation, and adapter behavior are implementation gates for S7-15
and S7-16. The deployment-owned master key must remain outside the application
datastore, browser, Git, and RDF.

## Secret Invariants

- Raw credentials never appear in API read responses, browser state after
  submit, browser storage, rendered DOM after submit, URL/query strings, client
  bundles, source-controlled files, `.env` committed to Git, general profile
  rows, RDF, fixtures, review packets, logs, traces, metrics, or telemetry.
- The browser sends a credential only over the settings write boundary. The
  server clears the request value as soon as the approved SecretStore operation
  completes; plaintext lifetime is minimized and zeroization is best effort at
  the runtime boundary.
- SecretStore failures are fail-closed and recoverable. The system does not
  activate metadata without a resolvable secret when live extraction requires
  one, and does not delete the known-good reference before replacement is
  durably stored.
- Provider payloads, authorization headers, and sensitive URL components are
  excluded from errors and configuration audit events.
- A secret reference is not a credential substitute in API responses. Clients
  receive only `credentialConfigured` and sanitized health state.

## Authorization and Audit Seam

The current local experience adapter is not authentication. Every settings
mutation and connection check must still carry server-established actor and
request correlation. The contract reserves a future authorization decision
before the operation is committed; it does not accept an actor ID from the
browser.

Allowed configuration audit fields:

- actor ID from trusted context;
- request ID and operation (`read`, `write`, `rotate`, `remove`, `test`);
- profile revision before/after where applicable;
- provider type and sanitized host identity only;
- outcome class, latency, and failure category.

Forbidden audit fields include raw credentials, secret references, provider
request/response bodies, authorization headers, prompt/note content, and
complete sensitive URLs.

## Cache and Rotation Rules

- A gateway uses one immutable snapshot for one extraction operation.
- Active profile changes do not require an application restart.
- A request already using revision `N` completes with revision `N`; a later
  request resolves revision `N+1`.
- Long-lived process/client caches must be keyed by profile revision and must
  not retain superseded plaintext credentials beyond the implementation's
  bounded cleanup window.
- Connection checks do not change the active profile or semantic data.

## Failure and Recovery Contract

| Failure | Required behavior |
|---|---|
| Missing/unsupported provider configuration | Fail closed with a sanitized configuration-unavailable result. |
| Invalid URL/model/provider | Return field-safe validation; retain prior active profile. |
| SecretStore unavailable | Do not activate new metadata; retain known-good profile if still usable and report retryable status. |
| Credential rotation conflict | Return a revision conflict; do not overwrite a newer profile. |
| Provider connection failure | Return sanitized health result; do not disable a known-good profile automatically. |
| Active credential removed | Mark profile unavailable/inactive; extraction fails closed until configured again. |
| API/network retry | Use idempotent operation semantics and request IDs; never log or replay raw credentials from telemetry. |

## Review Gates and Non-Goals

S7-07 must review the browser/API trust boundary, redaction, authorization
seam, and local-mode limits. S7-14 has approved application-encrypted
operational storage for the local baseline; S7-15/S7-16 must still add
persistence and dependencies only within that decision.

This contract does not implement application encryption, Vault, OS keyring,
PostgreSQL, a production secret manager, authentication, RBAC/ABAC, or a
provider beyond the current accepted types.
