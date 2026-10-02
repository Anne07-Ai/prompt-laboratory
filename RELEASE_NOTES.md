# Prompt Laboratory v0.10.0 — Team collaboration and role-based access

Prompt Laboratory v0.10.0 completes Phase 9C by turning workspace isolation into a usable,
permission-controlled collaboration model for prompt quality engineering teams.

## Added

- expiring, single-use workspace invitations bound to the invited email address
- authenticated invitation acceptance and rejection
- owner, admin, editor, and viewer workspace roles
- central permission checks for workspace-scoped API operations
- workspace member listing, role updates, and member removal
- final-owner protection against unsafe removal or demotion
- Streamlit member and pending-invitation management
- permission-aware dashboard controls for membership administration
- a two-user Docker Compose smoke workflow covering invitation, access denial, role promotion, and
  successful editor execution
- focused dashboard collaboration permission tests

## Security boundaries

- Invitation tokens are stored only as hashes and are returned in plaintext only at creation time.
- Invitations expire, are single-use, and are bound to the intended account email.
- Authorization decisions remain server-side; hidden dashboard controls are not treated as a
  security boundary.
- Cross-workspace access returns a generic denial and does not disclose resource existence.
- Viewers cannot execute prompts, create runs, or modify membership in that workspace.
- Editors can run experiments but cannot administer workspace membership.
- Admins cannot manage owners or peer admins.
- A workspace cannot lose its final owner through role update or member removal.
- Provider credentials remain encrypted with AES-256-GCM and are never returned in plaintext.
- Personal provider credentials remain account-scoped; workspace permissions determine whether a
  user may execute a prompt with them in the selected workspace.

## Verification

- 64 automated tests pass.
- Ruff static checks pass.
- GitHub CI and the prompt-quality regression gate pass.
- API and dashboard container builds pass.
- The Docker Compose smoke test validates a complete two-user collaboration workflow.

## Current scope

Version 0.10.0 remains an advanced self-hosted MVP. Password recovery, token revocation, managed
production hosting, billing, and controlled live A/B testing remain future work. GitHub remains the
engineering source of truth; a separate Hugging Face Docker Space is planned as a public,
mock-provider demonstration environment.
