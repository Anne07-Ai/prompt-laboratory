# Prompt Laboratory roadmap

The roadmap continues from the completed Phase 9C release. Each phase should be delivered through a
reviewed pull request with migrations, API tests, dashboard coverage, documentation, and passing
GitHub Actions checks.

## Current state — v0.10.0

Phases 1 through 9C are complete:

- Git-versioned prompt contracts and repeatable evaluation datasets
- deterministic and model-based evaluation with regression gates
- multi-provider execution and comparison
- FastAPI, Streamlit, PostgreSQL, and Docker Compose
- authenticated, workspace-isolated experiment history
- encrypted per-user provider credentials
- invitation-based team collaboration with role-based access
- permission-aware member management in the Streamlit dashboard
- two-user Docker Compose collaboration verification

## Phase 9C — Team collaboration and role-based access

Goal: turn workspace isolation into a usable multi-person collaboration model.

- [x] Create workspace invitations with expiry and single-use acceptance
- [x] Accept or reject an invitation as the authenticated invited user
- [x] List workspace members and pending invitations
- [x] Define owner, admin, editor, and viewer permissions
- [x] Enforce permissions centrally across workspace-scoped endpoints
- [x] Allow authorized users to change roles and remove members
- [x] Prevent removal or demotion of the final workspace owner
- [x] Add member and invitation management to the dashboard
- [x] Add the foundational Alembic migration and permission tests
- [x] Extend the Docker Compose smoke flow for two-user collaboration

### Phase 9C acceptance criteria

- A workspace owner can invite a second registered user without exposing sensitive account data.
- The invited user cannot access the workspace until accepting a valid invitation.
- Viewer users cannot create runs, execute prompts, or change membership in that workspace.
- Personal provider credentials remain account-scoped; workspace roles control whether they can be
  used to execute prompts in the selected workspace.
- Editor users can run experiments but cannot manage membership.
- Admin users can manage members but cannot remove or demote the final owner.
- Cross-workspace access returns a safe authorization response and never leaks resource existence.
- CI, prompt-quality checks, and the full Compose smoke flow pass.

Status: complete in v0.10.0. The implementation and release evidence are documented in
[docs/phase9c-team-collaboration.md](docs/phase9c-team-collaboration.md).

## Phase HF-1 — Public Hugging Face demonstration

Goal: provide a safe public product demonstration without turning the Space into a hosted
production environment.

- [x] Add a single-container Docker adapter for the FastAPI and Streamlit processes
- [x] Expose only the Streamlit surface on Hugging Face port `7860`
- [x] Use ephemeral SQLite storage and generated runtime secrets
- [x] Create anonymous isolated visitor sessions without collecting personal sign-up details
- [x] Enforce mock-only provider execution at the API boundary
- [x] Reject provider credential operations in public-demo mode
- [x] Add a public-data warning and demo-mode tests
- [ ] Create the `lakshmianne/prompt-laboratory` Docker Space
- [ ] Verify the live Space build and smoke workflow

The adapter and security decisions are documented in
[docs/hugging-face-space.md](docs/hugging-face-space.md).

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
