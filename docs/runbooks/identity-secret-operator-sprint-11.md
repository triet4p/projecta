# Sprint 11 identity and secret operator runbook

This runbook is for the early-production topology approved at G1. It assumes one
production-mode Keycloak instance, the existing PostgreSQL service with a
dedicated Keycloak database/user, and one single-node OpenBao integrated-Raft
instance. This topology is deliberately non-HA.

## Initial deployment

1. Provision the dedicated PostgreSQL database and user. Do not reuse the
   Projecta application database credentials for Keycloak.
2. Install the pinned Keycloak image from the approved digest, configure the
   external TLS reverse proxy, and expose only the OIDC protocol surface.
   Keep the admin console/API, health, and metrics on the private network.
3. Create the Projecta realm, public authorization-code client, exact callback
   URI, required `openid profile email` scopes, and mandatory S256 PKCE. The
   client has no reusable secret; keep one-time admin bootstrap material outside
   the repository and remove it after rotation.
4. Configure Projecta with the issuer, client ID, audience, callback URI, and
   session cookie settings. Resolve the public issuer hostname to the TLS edge
   on the shared service network and mount the edge issuer certificate/CA
   through `PROJECTA_API_OIDC_CA_FILE`; never bypass the public protocol surface
   or disable certificate verification.
   Projecta owns sessions and project membership; a Keycloak login does not
   grant project access by itself.
5. Start OpenBao with the pinned image, internal TLS, a dedicated volume, and
   integrated Raft. Never publish the API/UI/health/metrics port.

## OpenBao bootstrap and normal restart

1. Initialize once with three Shamir recovery shares and threshold two. Store
   each share offline in two independent operator-controlled locations.
2. Create the least-privilege Projecta policy and AppRole. The RoleID may be in
   deployment configuration; the single-use SecretID must be delivered through
   the Compose secret transport, with a short TTL.
3. Revoke the bootstrap/root token after policy and AppRole verification.
4. After a cold restart, two operators unseal OpenBao, verify TLS and health,
   then issue fresh bootstrap material if the previous SecretID was consumed.
   Manual unseal is an accepted residual operator dependency, not HA.

## Credential lifecycle

- Put the Teams certificate private key and related credential material in one
  untracked, permission-restricted JSON file. Include operator-chosen
  `projectId`, stable `installationId`, `tenantId`, `teamId`, `channelId`, and
  `credentialRevision`. Run
  `uv run --project apps/api python scripts/provision_teams_setup.py INPUT --operator-token-file TOKEN_FILE --output-handle-file HANDLE_FILE`.
  The command writes the credential to its installation-scoped OpenBao path,
  stores only a digest-backed single-use setup record in PostgreSQL, and writes
  only the opaque handle to `HANDLE_FILE`.
- Transfer the handle through the restricted operator channel and delete the
  handle file after successful consumption. The browser never receives the
  input JSON, provider identifiers, certificate, private key, OpenBao token, or
  secret reference.
- Rotate credentials by writing a new version, validating a test sync, then
  revoking the old version. Do not edit a secret reference in logs or tickets.
- Revoke a compromised AppRole SecretID immediately, issue a replacement, and
  record the correlation/request ID and safe outcome only.
- Keep workload tokens short-lived and revocable. Projecta sessions remain
  Projecta-owned and are not restored from a browser or provider token.

## Backup and restore

- Take an encrypted OpenBao snapshot daily and after every important credential
  change. Test restore access without printing snapshot contents.
- Back up Keycloak PostgreSQL and Projecta identity/membership state according
  to the database runbook. Record snapshot timestamps and operator IDs in the
  change record, never credentials.
- On a cold restore, restore user mapping and additive memberships, then
  invalidate all Projecta sessions (session epoch/revocation). Users must log
  in again; browser login state is intentionally not restored.
- Initial targets are RPO 24 hours and RTO 60 minutes. Escalate if restore
  verification cannot meet them; do not weaken TLS, dev mode, or policy scope.

## Diagnostics and stop conditions

Use request/correlation IDs and safe audit labels (`login`, `session`,
`membership`, `secret`, `connector`, `candidate`). Never paste JWTs, private
keys, SecretIDs, provider IDs, or raw Teams payloads into diagnostics. Stop and
escalate on unsealed storage without TLS, a public admin surface, a missing
session invalidation after restore, or a full-stack memory headroom below 20%.
