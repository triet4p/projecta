# Project Membership and Capability Policy — Sprint 11 S11-06

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-06

**Contract:** `projecta-membership.v1-draft`

## Scope

Sprint 11 adds the smallest server-owned project policy needed for sign-in,
review, and read-only connector installation. It does not create a general
tenant-admin product, policy language, or full RBAC/ABAC designer.

## Membership record

The authoritative record is PostgreSQL-owned and contains:

- internal user/actor key;
- internal project key;
- finite role set;
- active/revoked state;
- membership revision;
- created/updated timestamps;
- safe audit attribution.

Provider group claims may be an input to a reviewed seed/synchronization
workflow, but they do not directly become durable Projecta capabilities.

## Finite roles

| Role | Read project context | Review candidates | Manage Teams installation |
| --- | ---: | ---: | ---: |
| `project-reader` | Yes | No | No |
| `reviewer` | Yes | Yes | No |
| `connector-admin` | Yes | Only if separately granted by policy | Yes |

Roles are project-scoped and additive. A user may hold more than one role in
the same project and may have different roles in different projects. No role
implies access to another project, tenant, provider resource,
secret reference, raw evidence, or RDF graph outside the selected scope.

## Capability mapping

The policy exposes finite action decisions:

- `project.read` — authorized project catalog/context and safe retrieval;
- `candidate.review` — validate/confirm/reject eligible candidates;
- `connector.install` — create/update/enable/disable an allowlisted
  installation;
- `connector.run` — execute one bounded inbound import;
- `connector.read` — read safe installation/run status.

`connector-admin` is the only Sprint 11 role that can manage or run the Teams
installation. `reviewer` can review imported candidates but cannot alter the
installation or secret binding.

## Decision algorithm

Every protected operation performs:

1. active server session and non-expired principal check;
2. project membership lookup and current membership revision check;
3. finite role-to-capability decision;
4. installation ownership/type/revision check where applicable;
5. explicit operation budget and idempotency validation;
6. safe mapping to `401`, `403`, `404`, `409`, or bounded service failure.

The server rechecks policy immediately before each mutation or adapter call.
An earlier browser view, opaque handle, provider claim, or project hint is not
a durable grant.

## Isolation rules

- Invisible or cross-project installations, runs, evidence, and knowledge map
  to the same safe not-found behavior as an unknown resource.
- Counts, timings, errors, audit labels, telemetry, and UI fallback data must
  not reveal another project's existence.
- Secret references are checked against project, installation, connector type,
  provider tenant, and revision scope without revealing their value.
- Membership removal invalidates future operations and follows the chosen
  session refresh/revocation cadence.

## Administrative seed workflow

Initial memberships are seeded through an operator-controlled, auditable CLI
or file workflow in the deployment boundary. The input is untracked and
permission-restricted, or is delivered through an approved Compose secret.
The workflow is idempotent, revisioned, accepts only the three finite roles,
and does not create an admin UI.

After cold recovery, membership and user mapping are restored but all
Projecta sessions are invalidated. Users must sign in again.

## Explicit exclusions

- no generic policy expression language;
- no tenant-wide role inheritance;
- no provider group claim as sole authorization authority;
- no browser-controlled project, role, capability, actor, or tenant fields;
- no automatic identity merge by display name.
