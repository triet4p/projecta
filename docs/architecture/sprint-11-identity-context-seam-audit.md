# Identity and Context Seam Audit — Sprint 11 S11-03

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-03

## Current seams

| Seam | Current v0.5.1 behavior | Sprint 11 implication |
| --- | --- | --- |
| Request context | `TrustedRequestContext` and `TrustedActorContext` are populated from server-injected headers and correlation IDs | Replace the production source with a server-owned session/principal adapter; retain the port, not browser authority |
| Local experience | `LocalExperienceContextMiddleware` injects actor/project selection for `experience` mode and rejects production use | Keep for deterministic local/test flows; production must fail closed without reviewed OIDC |
| Connector principal | `ConnectorPrincipalPort` resolves principal, allowed projects, roles, capabilities, and correlation | OIDC session resolution should implement this port without changing connector orchestration |
| Connector policy | `LocalConnectorPrincipalAdapter` maps finite actions/capabilities and rejects `production` mode | Add a reviewed provider-backed adapter and server-owned membership source |
| Project selection | Experience selection store supplies project and revision through middleware | Browser selection becomes a navigation input; membership and capability are rechecked server-side before every operation |
| Public errors | Connector and semantic handlers map to bounded `401`/`403`/`404`/`409`/`503` problems | Preserve safe existence behavior for stale, invisible, and unauthorized resources |
| Secret binding | Installation stores an opaque `secret_...` reference resolved through `SecretStore` | Keep opaque binding; replace only the provider behind the port after S11-09/S11-10 approval |
| Audit/correlation | Request and operation IDs are generated/normalized before connector policy | Add session, membership, secret resolution, and provider run labels without raw identifiers or tokens |
| Browser surface | SPA calls same-origin typed API and currently has local experience/configuration states | Add sign-in/session-expiry/logout states without storing claims, tokens, or authorization authority |

## Authority flow after Phase A

```text
OIDC callback
→ validated provider subject
→ server session repository
→ production principal adapter
→ server-owned membership and capability policy
→ project/installation revision checks
→ bounded connector operation
```

The browser may provide only navigation inputs, a CSRF-protected mutation,
opaque handles, and expected revisions. It cannot provide actor, role,
capability, project, tenant, secret, graph, or trusted-context authority.

## Required implementation seams

1. A provider-neutral `ProductionPrincipalPort` or equivalent adapter must
   produce the existing `ConnectorPrincipal` shape.
2. Session persistence must live in PostgreSQL with expiry, revocation,
   subject mapping, safe audit attribution, and migration ownership.
3. OIDC discovery, issuer, audience, signature, state, nonce, PKCE, time,
   and redirect validation must complete before session creation.
4. Production composition must reject local context fallback, missing OIDC
   configuration, dynamic issuer/host trust, and stale membership.
5. Connector authorization must re-check membership and installation revision
   immediately before mutation or adapter execution.
6. The existing adapter contract must not receive a browser request, raw
   trusted headers, arbitrary network client, or RDF dataset.

## Boundary gaps to resolve before implementation

- exact internal user/subject/tenant mapping;
- whether refresh tokens are required for the bounded Teams app-only flow;
- session invalidation behavior after logout, provider revocation, and cold
  recovery;
- membership seed/admin workflow without a general tenant-admin product;
- OIDC discovery/JWKS availability and startup readiness behavior;
- canonical public session status and safe failure codes;
- migration coexistence between local experience/test and production adapters.

## Audit conclusion

The current code has a usable provider-neutral authorization seam, but it does
not yet provide production authentication. S11-15 through S11-29 may extend
the seam under the S11-14 approved Keycloak baseline and revised public/private
protocol boundary. No production identity implementation is claimed by this
audit.
