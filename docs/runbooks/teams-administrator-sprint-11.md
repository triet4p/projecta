# Sprint 11 Teams administrator runbook

This procedure configures one operator-controlled Microsoft 365 tenant, one
team, and one channel per Projecta installation. Projecta uses app-only
certificate authentication and read-only resource-specific consent.

## App registration and consent

1. Create or select the Microsoft Entra app registration owned by the tenant
   administrator. Create a certificate credential with an expiry and rotation
   owner; keep the private key out of source control and the browser.
2. Grant only application permission `ChannelMessage.Read.Group` and complete
   resource-specific consent for the selected team/channel. Do not grant
   `ChannelMessage.Read.All` for Sprint 11.
3. Verify the token audience and Graph host are the fixed Microsoft Graph
   endpoint. Redirect-based delegated login and refresh tokens are not used.
4. Put the private key and required credential bundle into OpenBao through the
   identity/secret operator runbook. The Projecta Connections screen accepts
   only the resulting opaque operator setup handle.

## Installation and controlled sync

1. Confirm the test channel contains only non-sensitive test messages and that
   the operator can remove consent later.
2. In Projecta, select Connections, review the least-privilege guidance, and
   submit the opaque setup handle. Verify the installation is initially
   disabled, then enable it with the current revision.
3. Run one manual sync. The adapter reads at most one root-message page with
   `$top=50`, up to 10 replies per root and 50 replies total, with the existing
   100-event, 10 MiB/run, 1 MiB/event, and 30-second absolute limits.
4. A bounded result is shown as `Completed with limits`/`truncated`; it is not a
   complete-success claim. Imported material continues only through Projecta's
   Review Queue and Knowledge surfaces.

## Rotation, removal, and diagnostics

- Before certificate expiry, write the replacement version to OpenBao, perform
  one test sync, then revoke the old certificate and token material.
- Disable the Projecta installation before removing team consent. Remove the
  resource-specific consent, certificate credential, and OpenBao secret only
  after the retention/change record is complete.
- Use request/correlation IDs and safe labels for credential, permission,
  provider-not-found, rate-limit, truncation, and terminal outcomes. Do not
  log tenant/team/channel IDs, Graph URLs containing resource IDs, attachments,
  hosted content, message bodies, certificates, or secret references.
- If permission is denied, re-check the exact RSC target and application
  permission rather than broadening permission. If the channel is unavailable,
  stop the installation and use the explicit retry after correcting setup.
