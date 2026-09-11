# Prompt Laboratory v0.6.0 — Open-source MVP

Prompt Laboratory treats prompts as production software: versioned in Git, validated against
typed contracts, evaluated on repeatable datasets, and protected by regression gates.

## Included

- versioned YAML prompts and strict Jinja2 rendering
- deterministic, similarity, schema, and LLM-judge evaluation
- OpenAI, Anthropic, local-compatible, and mock providers
- token, latency, cost, prompt-version, and model comparison
- automatic pull-request quality gates with auditable artifacts
- FastAPI evaluation ledger backed by PostgreSQL
- visual Streamlit experiment console
- reproducible Docker Compose environment
- six synthetic cross-industry demonstrations

## Scope boundaries

This release is an evaluation and release-confidence platform. Production traffic routing, hosted
authentication, team workspaces, billing, and live A/B testing are intentionally deferred.
