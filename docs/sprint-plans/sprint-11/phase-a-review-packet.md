# Sprint 11 Phase A Discovery Packet

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Scope:** S11-01 through S11-13 only

This packet collects the discovery outputs required before implementation.
G1 was approved with revisions on 2026-08-12. The approval record is
[S11-14 G1 approval](g1-approval.md). Implementation is authorized from
S11-15 onward only within that revised scope.

## Artifact index

| Task | Artifact | Outcome |
| --- | --- | --- |
| S11-01 | [v0.5.1 compatibility baseline](../../architecture/v0.5.1-compatibility-baseline.md) | Released surface frozen |
| S11-02 | [Teams read-only use case](../../use-cases/teams-read-only-channel.md) | Actors, bounds, journeys, counterexamples, non-goals |
| S11-03 | [Identity/context seam audit](../../architecture/sprint-11-identity-context-seam-audit.md) | Current seams and implementation gaps |
| S11-04 | [OIDC provider benchmark](../../architecture/oidc-provider-benchmark.md) | Keycloak 26.7.0 approved with digest pinning |
| S11-05 | [Production identity contract](../../architecture/production-identity-contract.md) | OIDC/session/principal contract approved with revisions |
| S11-06 | [Membership/capability policy](../../architecture/project-membership-capability-policy.md) | Additive finite roles and operator seed approved |
| S11-07 | [Identity threat model](../../architecture/identity-threat-model-sprint-11.md) | Public protocol/private management split approved |
| S11-08 | [Secret provider benchmark](../../architecture/secret-provider-benchmark-sprint-11.md) | OpenBao 2.6.1 approved with digest pinning |
| S11-09 | [Secret manager contract](../../architecture/secret-manager-contract.md) | Projecta authorization/OpenBao custody split approved |
| S11-10 | [OpenBao operations proposal](../../architecture/openbao-operations-proposal.md) | Raft/TLS/Shamir/AppRole/restore workflow approved |
| S11-11 | [Teams provider contract](../../architecture/teams-provider-contract.md) | Certificate app-only/RSC/bounded contract approved |
| S11-12 | [Teams threat model](../../architecture/teams-connector-threat-model.md) | Provider abuse/failure controls approved with revisions |
| S11-13 | [Ontology reuse audit](../../ontology/sprint-11-teams-reuse-audit.md) | `NO_ONTOLOGY_CHANGE_REQUIRED` approved |

## G1 decisions recorded

The recorded G1 selections are:

- identity provider and exact production image/version;
- secret provider, topology, workload authentication, and custody procedure;
- fixed hostnames/TLS/admin-surface topology and resource budgets;
- Teams permission model, tenant/channel scope, app registration, and bounds;
- membership seed workflow and session recovery semantics;
- ontology outcome and any required semantic governance work;
- residual acceptance of single-instance Keycloak/OpenBao and manual unseal.

Before the approval record was created, implementation tasks S11-15 onward
were blocked. They are now authorized within the revised G1 scope.

## G1 approval status

The prior pending list is superseded by the approval record. Implementation
still requires immutable image digests, TLS material, resource measurements,
clean-Compose acceptance, recovery evidence, and the security gates.
