# Free OIDC Provider Benchmark — Sprint 11 S11-04

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-04

## Decision question

Which identity boundary can provide production-shaped OIDC for Projecta
without requiring an Azure subscription, while preserving a provider-neutral
server session and the existing connector authorization seam?

## Options

| Option | Strengths | Costs/risks | Sprint 11 fit |
| --- | --- | --- | --- |
| Self-hosted Keycloak | OIDC, PostgreSQL, production hostname/TLS/readiness guidance, private admin surface, deterministic Compose boundary, migration seam to managed identity | Single instance is not HA; realm/client/bootstrap and operator upgrades are owned by Projecta | **Proposed baseline; pending G1** |
| Entra-backed Projecta login | Microsoft-native identity and Teams ecosystem alignment; less identity software to operate | Couples Projecta login to an external tenant, app registration, consent, and provider availability; weakens vendor-neutral local acceptance | Deferred alternative |
| Local experience/test context | Deterministic, credential-free, existing implementation and replay-friendly | Not production authentication; trusted-context secret and local configuration are not user identity or tenant isolation | Retain only for local/test |

## Evaluation criteria

- OIDC discovery, signed-token validation, issuer/audience controls, key
  rotation, logout/revocation, and session expiry;
- PostgreSQL and Docker Compose fit, fixed hostname, TLS, readiness, and
  private administration;
- bootstrap and recovery procedure, resource cost, upgrade path, and
  operator burden;
- local/test determinism without live provider dependency;
- migration path to a hosted or managed provider without changing browser,
  session, connector, or semantic contracts;
- license and current official operational guidance revalidated before G1.

## Proposed evaluation result

Keycloak `26.7.0` is the approved no-subscription baseline because it provides a
vendor-neutral OIDC issuer that can be operated inside the existing Compose
baseline while leaving Entra as a later adapter. This is not an approved
architecture baseline. The implementation must use the official
`quay.io/keycloak/keycloak:26.7.0` image and record its immutable digest after
pulling it. The database/user is isolated inside the existing PostgreSQL
boundary; no second PostgreSQL container is required.

## Guardrails for any selected provider

- issuer and audience are fixed deployment configuration, never derived from
  request headers or redirect URLs;
- admin APIs/console and health/metrics are private management surfaces;
- authorization/login and only the required discovery/JWKS protocol endpoints
  are separately exposed through the public OIDC hostname;
- production mode is distinct from development mode and has no local fallback;
- session ownership remains in Projecta PostgreSQL;
- public CI uses deterministic identity fixtures, not a live provider;
- provider replacement changes only the identity adapter/configuration boundary.

## Evidence required at G1

1. Current official production/container guidance and license review.
2. Compose topology with fixed public login hostname and private management
   hostname/path.
3. PostgreSQL isolation and least-privilege database grants.
4. Readiness and JWKS/discovery failure behavior.
5. Cold restart and restore assumptions, including the non-HA limitation.
6. Measured CPU/memory budget on the target single-VM profile, starting at
   2 GiB and 2 CPU for Keycloak with at least 20% full-stack headroom.

## References

- [Keycloak production configuration](https://www.keycloak.org/server/configuration-production)
- [Keycloak container guidance](https://www.keycloak.org/server/containers)
- [Projecta deployment choice](../initialization/08-Deployment-Choice.md)
