# Prompt Laboratory v0.9.0 — Secure multi-user workbench

Prompt Laboratory treats prompts as production software: versioned in Git, validated against typed
contracts, evaluated on repeatable datasets, and protected by regression gates.

## Included

- versioned YAML prompts and strict Jinja2 rendering
- deterministic, similarity, schema, and LLM-judge evaluation
- OpenAI, Anthropic, Gemini, local-compatible, and mock providers
- side-by-side provider comparison with token, latency, and cost evidence
- automatic pull-request quality gates with auditable artifacts
- FastAPI evaluation ledger backed by PostgreSQL or SQLite
- responsive Streamlit experiment workbench
- reproducible Docker Compose environment and full-stack smoke test
- email/password authentication with expiring signed access tokens
- workspace membership and workspace-isolated evaluation history
- persistent single-provider and comparison experiments
- versioned Alembic database migrations
- encrypted per-user OpenAI, Anthropic, and Gemini credentials
- six synthetic cross-industry demonstrations

## Security boundaries

- Provider credentials are encrypted with AES-256-GCM and bound to the owning user and provider.
- Plaintext provider keys are never returned by the API or stored in experiment evidence.
- Every workspace-scoped API operation verifies membership.
- Prompt YAML and approved baselines remain Git-reviewed source-controlled artifacts.
- The local PostgreSQL password in Docker Compose is for development only.

## Current scope

Version 0.9.0 is an advanced self-hosted MVP. Team invitation management, granular role enforcement,
password recovery, token revocation, managed hosting, billing, and live A/B testing remain future
work. See [ROADMAP.md](ROADMAP.md) for the planned sequence.
