# Connector Adapter Contract — Sprint 10

**Status:** `G1_APPROVED_IMPLEMENTATION`

**Task:** S10-04

**Contract version:** `connector-contract.v1`

## Purpose and boundary

This contract defines the provider-neutral port between Application API
orchestration and a connector adapter. An adapter translates one source
system's bounded inbound behavior into canonical events and evidence
references. It does not decide Projecta authorization, create domain facts,
write RDF, advance a cursor, retry an operation, or expose provider payloads to
the browser.

The first implementation is the deterministic JSON/Mock adapter. The same port
must be usable by a future live adapter without changing the canonical event,
operational-state, evidence, Semantic Core, or public projection contracts.

## Adapter descriptor and finite capabilities

Each adapter exposes a stable descriptor through the registry:

```text
ConnectorDescriptor
├── connectorType: allowlisted opaque type
├── contractVersion: connector-contract.v1
├── displayName: bounded user-facing label
├── capabilities: finite set
└── limits: adapter limits that cannot exceed server policy
```

The v1 capability vocabulary is:

| Capability | Meaning | JSON/Mock |
| --- | --- | --- |
| `inbound-import` | Pull bounded source changes and emit canonical events | Supported |
| `resource-fetch` | Fetch bounded source content referenced by an event | Supported within the approved local fixture boundary |
| `identity-hint` | Return a non-authoritative external identity hint | Optional/no automatic merge |
| `cancellation` | Observe the server cancellation token and stop at a safe boundary | Required |
| `outbound-action` | Send messages, create tasks, upload artifacts, or cause external side effects | Not supported in Sprint 10 |

Unknown capabilities, duplicate descriptors, provider-specific capability
strings, and capability escalation at runtime fail closed. A capability
description is safe metadata; it never includes credentials, provider scopes,
storage paths, arbitrary execution, or administrative privileges.

## Typed port

The conceptual async port is:

```python
class ConnectorAdapter(Protocol):
    def descriptor(self) -> ConnectorDescriptor: ...

    async def validate_installation(
        self,
        config: InstallationConfig,
        context: AdapterContext,
    ) -> InstallationValidation: ...

    async def pull_events(
        self,
        command: PullEventsCommand,
    ) -> PullEventsResult: ...

    async def fetch_resource(
        self,
        command: FetchResourceCommand,
    ) -> ResourceResult: ...

    async def resolve_identity_hint(
        self,
        command: IdentityHintCommand,
    ) -> IdentityHintResult: ...
```

The production Python implementation must use fully typed models and
provider-neutral ports. The adapter must not receive a browser request, raw
trusted headers, an RDF dataset, a Semantic Core client, or a general-purpose
filesystem/network client.

## Installation validation

`validate_installation` is a bounded, explicit operation that checks only the
allowlisted installation configuration and declared capability. It returns a
finite result:

- `valid` — configuration is structurally valid and the declared capabilities
  are available;
- `invalid` — a safe allowlisted field/code explains what must be corrected;
- `unsupported` — the requested capability or configuration mode is not part
  of this adapter;
- `unavailable` — a bounded dependency check could not complete;
- `cancelled` or `deadline-exceeded` — the outer operation ended.

Validation does not silently enable an installation, create secrets, contact
an arbitrary external endpoint, or persist an operational row. The service
layer owns installation state, policy, revision, audit, and enable/disable
transitions.

## Bounded pull/import

`pull_events` receives a server-created command containing:

- selected connector type and installation binding;
- an opaque cursor or `None` for the initial position;
- a finite event and byte budget;
- one absolute deadline and cancellation token;
- correlation and operation IDs for telemetry only;
- the capability explicitly authorized for this attempt.

It returns one result containing:

- zero or more bounded adapter event candidates;
- an opaque source cursor candidate, if the adapter has one;
- source count/byte counters;
- one terminal adapter outcome.

The adapter must:

- call the source exactly once for this attempt;
- honor the absolute deadline and cancellation token;
- never add SDK, HTTP, proxy, scheduler, worker, or recursive retries;
- never process beyond the supplied event/byte/item limits;
- emit only data that can be validated into the canonical event contract;
- return the cursor as opaque bytes/string without parsing or rewriting it;
- leave cursor commit to the orchestration transaction after evidence and
  Semantic Core commit.

An empty result is valid only when the bounded pull completed successfully. It
is not a hidden failure or permission fallback.

## Resource fetch

`fetch_resource` accepts only an event-associated opaque external reference
that was returned by the adapter and is authorized for the same installation
and project. It returns bounded content metadata/bytes for the evidence port,
not a domain object.

The adapter must reject:

- arbitrary filesystem paths, path traversal, local device paths, or object
  store keys;
- a reference from another installation/project;
- content above the server byte budget or outside the declared media allowlist;
- a resource that requires an unbounded redirect, pagination, or retry loop;
- a request after cancellation or the absolute deadline.

The evidence adapter verifies the content digest and stores the bytes. The
connector adapter does not decide retention, public visibility, semantic
provenance, or deletion.

## Identity hint

`resolve_identity_hint` is optional and non-authoritative. It may return a
bounded external identity reference, display label, source system, and an
ambiguity state. It may not:

- authenticate a Projecta principal;
- select a project or bypass policy;
- merge identities by display name;
- create a `Person`, `Team`, or assertion in RDF;
- return another project's existence;
- call an unbounded directory or external graph.

The application/semantic lifecycle treats the result as a source hint or
reviewable candidate. Human confirmation is required for ambiguous identity
links.

## Cursor contract

The adapter may return an opaque cursor candidate with a bounded size. The
orchestrator stores it only after all corresponding source/evidence and
Semantic Core work commits. A cursor is not a page number, database key, RDF
identifier, or public handle.

Cursor behavior is fixed:

- initial `None` means the adapter's authorized initial position;
- unchanged cursor means no committed source advancement;
- a candidate cursor is proposed once per successful pull;
- cursor advancement is exactly once for the committed event batch;
- validation, conflict, timeout, cancellation, storage, Semantic Core, or
  dead-letter failure leaves the previous cursor unchanged;
- replay returns the original committed cursor outcome without advancing again.

The adapter never commits its own cursor and never accepts a browser-supplied
cursor as authority.

## Cancellation and deadline behavior

Every method receives one operation deadline from the outer orchestration
boundary. Nested budgets must be derived from the remaining time; no child
operation may extend the outer deadline. Cancellation is cooperative but must
be observed at the start of the method, before each bounded external/resource
step, and before returning a result.

Terminal outcomes are finite:

- `succeeded`
- `empty`
- `cancelled`
- `deadline-exceeded`
- `invalid-installation`
- `unsupported-capability`
- `malformed-output`
- `unavailable`
- `rate-limited`
- `failed`

The adapter returns one outcome only. It must not conceal an exception as an
empty result, convert a storage/Core failure into success, or retry until the
outer boundary times out.

## Typed adapter errors

Safe error codes are allowlisted:

- `ADAPTER_UNKNOWN_TYPE`
- `ADAPTER_DUPLICATE_REGISTRATION`
- `ADAPTER_CONTRACT_UNSUPPORTED`
- `ADAPTER_INSTALLATION_INVALID`
- `ADAPTER_CAPABILITY_UNSUPPORTED`
- `ADAPTER_SCOPE_INVALID`
- `ADAPTER_REFERENCE_INVALID`
- `ADAPTER_OUTPUT_INVALID`
- `ADAPTER_LIMIT_EXCEEDED`
- `ADAPTER_CANCELLED`
- `ADAPTER_DEADLINE_EXCEEDED`
- `ADAPTER_UNAVAILABLE`
- `ADAPTER_RATE_LIMITED`
- `ADAPTER_FAILED`

An error carries code, correlation, safe bounded detail, retry classification,
and timestamp. It never carries raw source payloads, credentials, SQL, RDF
IRIs, stack traces, provider SDK objects, filesystem paths, or hidden retry
counts. The orchestration layer maps it to a terminal run/dead-letter outcome.

## Registry and dependency direction

The registry resolves an adapter only from an explicit allowlisted
`connectorType`. It rejects duplicates and unknown types before execution.

```text
Application API / connector service
        ↓ provider-neutral port
Connector registry → JSON/Mock adapter
        ↓ canonical events + bounded evidence result
Operational state + Evidence port + Semantic Core service
```

Semantic Core depends on canonical source/provenance contracts, not on the
registry or any provider module. Provider code is isolated behind the adapter
port and cannot become a semantic dependency or a browser capability.

## G1 decisions required

The following remain explicit human decisions at S10-10:

- whether the first runtime stays inside the Application API process or uses a
  separate deployable runtime;
- the final adapter limit defaults and capability descriptions;
- the installation validation dependency checks allowed in local/CI mode;
- the exact public status/problem projection derived from these internal
  outcomes.
