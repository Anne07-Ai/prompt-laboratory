# Phase 9A — Authentication and workspaces

Phase 9A introduces the identity boundary required before Prompt Laboratory can be deployed for
multiple contributors.

## Security model

- Email addresses are normalized before storage.
- Passwords are hashed with Python's scrypt implementation and a unique random salt.
- Password values and password hashes are never returned by the API.
- Access tokens are signed with HMAC-SHA256 and expire after eight hours.
- The signing secret is supplied through `PROMPT_LAB_AUTH_SECRET` and is never committed.
- Protected API routes require an `Authorization: Bearer <token>` header.
- Workspace routes additionally require `X-Workspace-ID`.
- Every workspace access is checked against the membership table.

## Persistence model

The database now contains users, workspaces, workspace memberships, and workspace-owned evaluation
runs. A new account automatically receives an owner membership in its first workspace. Users may
create additional workspaces.

Existing evaluation rows are retained as unscoped legacy data. They are not returned through an
authenticated workspace query.

## Dashboard flow

The Streamlit console presents sign-in and registration forms before loading prompt or provider
data. After authentication, the selected workspace is included with every experiment and run-history
request. Signing out removes identity, token, workspace, and cached result data from the Streamlit
session.

## Deployment requirements

Set a unique secret before starting the services:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Store the result as `PROMPT_LAB_AUTH_SECRET` in the local `.env` file or the deployment secret
manager. Never commit the value.

Phase 9A intentionally does not store provider API keys per user. Encrypted bring-your-own-key
support remains Phase 9B.
