# Sprint 11 G1 Approval — With Revisions

**Status:** `APPROVED_WITH_REVISIONS`

**Task:** S11-14

**Approved:** 2026-08-12

## Approval

Approve Sprint 11 G1 with revisions. Authorize implementation from S11-15
onward within the boundaries below. This approval does not approve G2, G3,
release `v0.6.0`, HA, unattended cold restart, or any deferred connector
capability.

## Selected baselines

| Boundary | Approved baseline | Required implementation evidence |
| --- | --- | --- |
| Identity | Keycloak `26.7.0`, official `quay.io/keycloak/keycloak:26.7.0`, production mode, digest-pinned after pull | Image digest, optimized non-root image, TLS, readiness, PostgreSQL isolation, no `start-dev` |
| Identity topology | One Keycloak instance with a separate PostgreSQL database/user; Projecta owns sessions and memberships | Same PostgreSQL service may host the database, but credentials/schema ownership are isolated |
| Secret manager | OpenBao `2.6.1`, `ghcr.io/openbao/openbao:2.6.1`, digest-pinned | TLS, private network only, non-root image, integrated Raft volume, health/readiness |
| Unseal | Shamir 3 recovery shares, threshold 2, stored in two independent offline locations | No tracked shares/root token; manual unseal and custody drill |
| Workload auth | AppRole; RoleID is non-secret, single-use SecretID with short TTL, short-lived renewable/revocable workload token | Bootstrap/revocation tests and no secret leakage |
| Teams auth | App-only client credentials using a certificate; private key stored in OpenBao | No delegated login, refresh token, or browser credential |
| Teams permission | Application `ChannelMessage.Read.Group` with resource-specific consent | Consent and exact tenant/team scope evidence |
| Teams scope | One tenant, team, and channel per installation | Internal binding and cross-scope negative tests |
| Membership | Existing three roles, additive assignment, operator-seeded CLI/untracked file, no admin UI | Finite-role validation, revisioned idempotent seed, audit evidence |
| Recovery | Restore membership/configuration but invalidate all Projecta sessions; require login again | Session epoch/revocation evidence after cold restore |
| Ontology | `NO_ONTOLOGY_CHANGE_REQUIRED` | No new vocabulary or ontology version change |
| Availability | Single-instance Keycloak/OpenBao and manual unseal accepted for early production only | Explicit residual-risk record; no HA/unattended-restart claim |

## Trust-boundary revisions

### Identity protocol versus management surfaces

The public edge exposes only the OIDC protocol surface required by the
application: authorization/login, and discovery/JWKS where the client or
protocol requires them. Keycloak admin console/API, health, and metrics remain
private management surfaces. The Projecta callback is an Application API route
on `projecta.example.com`; it is not a Keycloak administration surface.

```text
Internet
  └─ TLS reverse proxy
       ├─ projecta.example.com → Web/API and OIDC callback
       └─ auth.example.com      → required OIDC protocol endpoints only

Private Compose network
  ├─ Keycloak
  ├─ OpenBao
  ├─ PostgreSQL
  ├─ Semantic Core
  └─ Fuseki
```

All Keycloak administration, health, and metrics endpoints are private. The
same rule applies to all OpenBao, PostgreSQL, Fuseki, and Semantic Core
surfaces.

### OpenBao custody versus Projecta authorization

OpenBao is a service-level custody boundary. It protects runtime secret
storage, versioning, workload authentication, and revocation. Projecta remains
the authority for exact project, installation, connector-type, provider-tenant,
and installation-revision authorization. OpenBao policies must not be claimed
to enforce per-installation authorization unless that policy topology is
actually implemented and tested.

## Resource and recovery constraints

- Keycloak initial limit: 2 GiB and 2 CPU.
- OpenBao initial limit: 512 MiB and 0.5 CPU.
- No second PostgreSQL container; use isolated database/user ownership in the
  existing PostgreSQL boundary.
- Acceptance must retain at least 20% memory headroom. Failure reopens the
  benchmark; it must not weaken production mode.
- OpenBao snapshots target daily cadence and after material credential changes.
- Initial recovery target: RPO 24 hours and RTO 60 minutes.
- Cold restart requires operator unseal and renewed workload bootstrap. All
  Projecta sessions are invalidated after restore and users sign in again.

## Teams limits

The adapter retains the Sprint 10 limits:

- maximum 100 events per run;
- maximum 10 MiB per run and 1 MiB per event;
- absolute 30-second deadline;
- `$top=50` and at most one root-message page in the initial slice;
- maximum 10 replies per root and 50 replies total;
- root plus replies never exceed 100 events;
- reaching a bound returns `truncated`, not complete success;
- attachments and hosted content are not fetched; only safe metadata may be
  retained.

## Provider maturity and semantic approval

For the amended `v0.6.0` release target, GitHub Public Issues is the live
credential-free connector. Microsoft Teams remains experimental/deferred:
its adapter and deterministic regression tests are retained, but its live
sandbox journey is not a release gate and no work-tenant flow may be used.

The proposed `NO_ONTOLOGY_CHANGE_REQUIRED` outcome is approved for this
scope. Teams remains source/evidence ingestion, operational connector state
stays outside RDF, and no Teams-specific class/property/individual is added.

## Residual risk acceptance

The approval explicitly accepts single-instance identity/secrets and manual
OpenBao unseal for early production. It does not claim HA, automatic failover,
or unattended cold restart. These risks must remain visible in G2 and release
records.
