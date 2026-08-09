# Explicit Retry Contract — Sprint 8

**Status:** `PROPOSAL_ONLY` — pending S8-11 architecture/security approval
**Task:** S8-05

## Decision

The interactive product path is **single-attempt by default**. One extraction
request performs one live provider attempt, one normalization path, and one
semantic persistence path. If the attempt fails, the API returns its
normalized terminal problem; it does not retry, switch provider, switch model,
activate replay, store raw text, or manufacture an empty result.

The existing bounded `ResilientGateway` remains useful as a reusable mechanism,
but it is not permission to retry the product path. Its default construction
must be changed or guarded by an explicit reviewed operation mode before S8-14
implementation.

## Retry modes

| Mode | Owner/authorization | Eligible operation | Policy | User visibility |
| --- | --- | --- | --- | --- |
| `interactive-single-attempt` | Product runtime contract; default | Live extraction and semantic writes | `maxAttempts=1`; no automatic retry. | Final result/error includes request ID; attempt event is `1`. |
| `explicit-user-retry` | User presses Retry or resubmits intentionally | A previously failed or stale interactive operation | New visible action; preserves idempotency/revision rules. | Button/action and new request/operation correlation are visible. |
| `offline-replay` | Test/evaluation configuration only | Deterministic fixture execution | No network retry; fixture lookup is deterministic and finite. | Mode is visible in config/logs; never activated by a live failure. |
| `live-quality-evaluation` | Evaluation runner and approved Sprint 5 decision | Offline/live quality gate only | At most one bounded retry for `invalid_evidence`, as already approved for the evaluation runner; not product behavior. | Evaluation report records attempt count and mode. |
| `health-probe` | Compose/orchestrator probe scheduler | Liveness/readiness checks | Repeated probes are health sampling, not a hidden user operation; each probe has a timeout and event. | Readiness remains `not_ready` until a probe succeeds. |
| `operator-recovery` | Explicit runbook command | Recovery/diagnostic operations | Operation-specific and bounded; never silently attached to a user write. | Command, mode, scope, attempt, and outcome are logged. |

No other retry mode is approved by this task. Background jobs, connector
delivery, and outbound actions are Sprint 9+ concerns.

## Retry authorization rules

1. The operation mode is selected by server/deployment configuration or an
   explicit runbook/test command, never by an arbitrary browser field.
2. A mode must declare an integer `maxAttempts`, deadline, eligible internal
   error classes, idempotency behavior, and terminal outcome mapping.
3. `maxAttempts` is bounded to `1` for interactive writes and to the reviewed
   budget of the selected test/recovery mode; unbounded loops are invalid.
4. Every attempt emits `provider.attempt.started` and
   `provider.attempt.completed` under one operation ID, with the one-based
   attempt number and no raw payload.
5. The public response is returned only after the final attempt has a typed
   success or terminal problem. Intermediate failures cannot become success.
6. Any retry of a semantic mutation must use idempotency/revision protection;
   it must never create a second Note, candidate, assertion, or provenance
   chain for the same logical request.
7. Provider/model/base URL selection is frozen for one operation. A retry does
   not switch configuration or profile revision.

## Eligible error classes

| Internal class | Interactive path | Explicit reviewed mode | Rationale |
| --- | --- | --- | --- |
| `provider.timeout` | No automatic retry | Allowed only where mode declares a bounded retry | Timeout may be transient but can duplicate cost/mutation. |
| `provider.rate_limited` | No automatic retry | Allowed only with explicit backoff and budget | Retry-after policy is provider/mode-specific. |
| `provider.connection` / `provider.service` | No automatic retry | Allowed for non-mutating evaluation or operator recovery | Must not hide outage in product path. |
| `provider.schema_invalid` | No | No generic retry | Retrying malformed output hides contract/model defects. |
| `provider.unsafe_output` / `semantic.*` | No | No | Safety/semantic failures require correction, not repetition. |
| `invalid_evidence` in live quality runner | No | One bounded runner retry only | Existing approved Sprint 5 evaluation exception; it is not a product fallback. |
| `persistence.*` / `semantic_core.*` during write | No | No implicit retry | Write retry may duplicate or obscure transaction state. |
| `query.*` on read | No | Only an explicit operator/read recovery policy | A failed read must not become stale/empty success. |

The current provider adapter marks some schema/status failures as retryable for
the generic resilience helper. S8-14 must make retryability mode-aware and
ensure interactive construction cannot consume that generic flag as permission
to retry.

## Explicit user retry and idempotency

- A visible Retry action creates a new request/operation correlation but does
  not change project scope, provider profile, model, or source content.
- If the outcome of a prior mutation is unknown, the client reuses the same
  idempotency key so the server can return the original success or conflict
  rather than creating a duplicate.
- If the user intentionally requests a fresh extraction after a confirmed
  terminal failure, the client may create a new idempotency key; the UI must
  make that a new attempt and preserve provenance linking it to the source
  operation where the approved contract supports it.
- A browser refresh is not permission for a background retry. It reloads the
  typed operation state or reports the existing problem.

## Replay boundary

Replay is a deterministic test mode selected before the operation begins. A
live provider failure must never cause:

- a change from live provider to `replay:<case>`;
- a switch to a different provider, endpoint, model, prompt, or schema;
- a raw-text capture fallback;
- an empty/abstained result unless the provider explicitly returned a valid
  abstention before failing elsewhere;
- a successful response whose event says the live operation failed.

Replay must be visible in configuration and correlated events. It must not be
accepted as evidence of live-provider availability or production readiness.

## Timeout and budget contract

Every retry-capable mode declares:

- total operation deadline;
- per-attempt timeout;
- maximum attempts;
- backoff schedule and maximum delay;
- eligible error classes;
- idempotency/mutation rule;
- terminal public code/outcome;
- event schema and attempt count.

The total deadline includes backoff. An attempt that would exceed the deadline
is not started; the operation returns the appropriate timeout/failure class.

## Regression requirements

1. Interactive extraction invokes the provider exactly once for timeout,
   rate-limit, connection, schema, unsafe-output, and semantic failures.
2. Explicit user Retry is visible and does not duplicate a successful
   idempotent mutation.
3. A live failure never activates replay or another provider/model.
4. Evaluation-only `invalid_evidence` retry is bounded to one and cannot be
   imported into the application composition.
5. Attempt events use one operation ID, increasing `attempt`, and one final
   terminal outcome.
6. Readiness probes may repeat but never report ready from a failed probe.
7. Tests assert no raw prompt/source/provider payload in retry logs or public
   problems.

## Review status

This decision is an input to the S8-10 architecture/security/semantic packet.
It is proposal-only until G1 and must be implemented before S8-14 removes the
current product-path retry behavior.
