# Phase 9C — Team collaboration and role-based access

## Outcome

Phase 9C converts workspace isolation into a practical multi-user collaboration model. Teams can
invite registered users, assign bounded roles, review membership, and administer access without
weakening the existing workspace or provider-credential trust boundaries.

## Collaboration lifecycle

1. An owner or admin creates an invitation for an email address and an invit-able role.
2. The API returns the invitation token once and stores only its cryptographic hash.
3. The intended authenticated user accepts or rejects the invitation before expiry.
4. Acceptance creates the workspace membership exactly once.
5. Subsequent API and dashboard operations use the centrally enforced role permissions.

Invitations cannot assign the owner role. Owner transfer is intentionally outside this workflow so
that a separate, auditable ownership-transfer design can be introduced later.

## Role model

| Role | Read workspace | Run experiments | Manage personal credentials | Manage members |
|---|---:|---:|---:|---:|
| Owner | Yes | Yes | Yes | Yes |
| Admin | Yes | Yes | Yes | Yes, excluding owners and peer admins |
| Editor | Yes | Yes | Yes | No |
| Viewer | Yes | No | Yes | No |

The API is the enforcement point. Dashboard visibility improves usability but never substitutes for
server-side authorization.

## Dashboard experience

The Streamlit collaboration panel shows the selected workspace role and member list. Owners and
admins can create invitations, review pending invitations, update permitted member roles, and
remove permitted members. Invited users can submit their single-use token to accept or reject an
invitation.

The dashboard does not display stored invitation tokens or provider credentials. A newly generated
invitation token is shown once so it can be shared through an appropriate secure channel.

## Security and isolation controls

- invitation tokens are hashed before persistence
- invitations expire after seven days and cannot be reused
- invitation acceptance is bound to the authenticated user's normalized email address
- workspace membership is checked for every workspace-scoped operation
- forbidden cross-workspace operations return a generic access-denied response
- viewers cannot execute prompts or create evaluation runs
- editors cannot administer members
- admins cannot change owners or peer admins
- the final owner cannot be removed or demoted
- provider API keys remain encrypted and scoped to their owning user

Personal provider credentials are account-scoped rather than workspace-owned. A viewer may rotate
or remove their own key, but cannot use it to execute prompts in a workspace where their role lacks
the run-experiment permission.

These controls follow least privilege and defence-in-depth principles. They reduce unauthorized
workspace access, privilege escalation, resource enumeration, and accidental administrative
lockout risks.

## Verification evidence

The automated suite covers invitation lifecycle, email binding, expiry behaviour, permission
mapping, membership updates, member removal, final-owner protection, and dashboard target
filtering.

The Docker Compose smoke workflow validates the integrated path:

1. register an owner and a separate collaborator
2. verify the collaborator is denied before invitation acceptance
3. invite the collaborator as a viewer
4. accept the invitation and verify membership
5. verify that the viewer cannot execute a prompt
6. promote the collaborator to editor
7. verify successful prompt execution

The Phase 9C release gate requires Ruff, the complete test suite, API and dashboard container
builds, the prompt-quality regression gate, and the Compose collaboration smoke workflow to pass.

## Deferred scope

- explicit workspace ownership transfer
- invitation revocation and resend workflows
- email delivery integration
- authentication hardening, including password recovery and token revocation
- managed production deployment and operational monitoring
