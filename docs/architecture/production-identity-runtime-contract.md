# Production Identity Runtime Contract — Sprint 11

Status: `G1_APPROVED_WITH_REVISIONS` — S11-15 through S11-29 implementation

Projecta keeps the downstream `TrustedRequestContext` seam, but production
resolves it from an opaque server session and server-owned project membership.
The browser never supplies actor, project, role, capability, or trusted-context
headers. The local experience adapter remains explicitly unavailable in
production.

The OIDC boundary uses Keycloak `26.7.0`, PKCE S256, short-lived single-use
login state, nonce, bounded same-origin return paths, issuer/audience/time
validation, RS256 JWKS verification, and a server-side authorization-code
exchange. ID-token claims and provider tokens are not returned to the browser.

Projecta stores only opaque session state, subject/actor/tenant mapping, expiry,
revocation, CSRF material, and additive project memberships. Session cookies are
secure, HttpOnly, SameSite=Lax, bounded, and rotated at login. Mutating browser
requests require the session-bound CSRF token. Logout revokes the local session;
expired or revoked sessions cannot fall back to local context.

The PostgreSQL migration file is `0005_identity_sessions_memberships.py` with
the bounded Alembic revision ID `0005_identity_sessions`. The existing
Projecta PostgreSQL service owns these tables; Keycloak uses a separate database
and database user in that same service. Membership seed input is an operator
controlled untracked JSON file and accepts only `project-reader`, `reviewer`,
and `connector-admin`. Roles are additive.

Production readiness fails closed until Semantic Core and OIDC discovery plus a
non-empty signing-key set are usable. Discovery/JWKS are public protocol
surfaces through the fixed TLS edge; Keycloak administration, health, metrics,
PostgreSQL, and internal services remain private.
