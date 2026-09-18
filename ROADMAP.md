# Prompt Laboratory roadmap

The roadmap continues from the completed Phase 9B release. Each phase should be delivered through a
reviewed pull request with migrations, API tests, dashboard coverage, documentation, and passing
GitHub Actions checks.

## Current state — v0.9.0

Phases 1 through 9B are complete:

- Git-versioned prompt contracts and repeatable evaluation datasets
- deterministic and model-based evaluation with regression gates
- multi-provider execution and comparison
- FastAPI, Streamlit, PostgreSQL, and Docker Compose
- authenticated, workspace-isolated experiment history
- encrypted per-user provider credentials

## Phase 9C — Team collaboration and role-based access

Goal: turn workspace isolation into a usable multi-person collaboration model.

- [ ] Create workspace invitations with expiry and single-use acceptance
- [ ] Accept or reject an invitation as the authenticated invited user
- [ ] List workspace members and pending invitations
- [ ] Define owner, admin, editor, and viewer permissions
- [ ] Enforce permissions centrally across workspace-scoped endpoints
- [ ] Allow authorized users to change roles and remove members
- [ ] Prevent removal or demotion of the final workspace owner
- [ ] Add member and invitation management to the dashboard
- [ ] Add an Alembic migration plus isolation and authorization tests
- [ ] Extend the Docker Compose smoke flow for two-user collaboration

### Phase 9C acceptance criteria

- A workspace owner can invite a second registered user without exposing sensitive account data.
- The invited user cannot access the workspace until accepting a valid invitation.
- Viewer users cannot create runs, execute prompts, manage credentials, or change membership.
- Editor users can run experiments but cannot manage membership.
- Admin users can manage members but cannot remove or demote the final owner.
- Cross-workspace access returns a safe authorization response and never leaks resource existence.
- CI, prompt-quality checks, and the full Compose smoke flow pass.

## Phase 9D — Prompt review and approval

- [ ] Draft, review, approved, rejected, and superseded prompt states
- [ ] Reviewer identity, comments, and audit history
- [ ] Explicit baseline promotion
- [ ] Approval checks before release/export

## Phase 10 — Authentication hardening

- [ ] Email verification and password recovery
- [ ] Refresh-token or server-side session lifecycle
- [ ] Logout and token revocation
- [ ] Login rate limiting and security audit events

## Phase 11 — Hosted production deployment

- [ ] Managed PostgreSQL, HTTPS, and secret management
- [ ] Automated migration deployment and backups
- [ ] Monitoring, structured logs, alerting, and error reporting
- [ ] Deployment runbook and rollback procedure

## Phase 12 — Product expansion

- [ ] Organisation administration and usage limits
- [ ] Approved-prompt export and application integrations
- [ ] Billing controls
- [ ] Controlled live A/B testing
