# Phase 9A.1 — Database migrations and experiment persistence

This phase replaces ad-hoc schema creation with versioned Alembic migrations and records authenticated
workbench activity as workspace-owned experiment evidence.

## Migration lifecycle

- New databases are upgraded from the first baseline revision to the latest schema.
- Existing Phase 9A databases without an Alembic revision are stamped at the compatible baseline,
  then upgraded normally.
- Unexpected unmigrated schemas fail closed instead of being modified silently.
- Migration assets are packaged in the API container and run during application startup.

## Experiment records

Successful single-model and comparison requests now create an immutable experiment record containing:

- authenticated user and workspace ownership
- prompt ID and semantic version
- execution mode
- rendered prompt
- validated request variables and provider selection
- model output, provider/model identity, latency, tokens, cost, and comparison errors

The API returns the generated `experiment_id`. Workspace-scoped list and detail endpoints make the
evidence available without exposing it to users outside that workspace.

## API

- `GET /api/v1/experiments`
- `GET /api/v1/experiments/{experiment_id}`

Both endpoints require authentication and `X-Workspace-ID`.
