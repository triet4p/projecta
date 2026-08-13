# Identity and Edge Deployment Contract — Sprint 11

The production profile uses an optimized non-root Keycloak image, immutable
image references, internal health/metrics, and no `start-dev` command. The
reviewed Keycloak source tag is `quay.io/keycloak/keycloak:26.7.0`; the
production environment pins the pulled Linux/amd64 manifest by digest.

The reverse proxy accepts only the fixed `projecta.example.com` and
`auth.example.com` hostnames. It overwrites forwarded host/protocol/for headers,
routs the Projecta API and web app only on the Projecta hostname, and forwards
only the Projecta realm OIDC discovery, authorization, token, and logout
protocol paths on the auth hostname. Unknown hosts, management paths, health,
and metrics are rejected or private.

No second PostgreSQL container is introduced. The repeatable initialization
script creates the Keycloak role/database boundary from deployment-injected
values and revokes public database access. Keycloak bootstrap credentials are
not in the realm template; they are injected for controlled setup and removed
or rotated after bootstrap.

The accepted availability boundary remains single-instance Keycloak and
manual-operator recovery. This contract does not claim HA, unattended unseal,
or dynamic host routing.
