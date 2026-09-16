# Phase 8.1 — multi-provider comparison

Phase 8.1 extends the comparison workbench with current cost-efficient models from OpenAI,
Anthropic, and Google. The same rendered prompt can be sent concurrently to any two or more
configured providers.

## Supported live models

| Provider | Workbench model | Environment variable |
|---|---|---|
| OpenAI | GPT-4.1 mini | `OPENAI_API_KEY` |
| Anthropic | Claude Haiku 4.5 | `ANTHROPIC_API_KEY` |
| Google | Gemini 3.5 Flash-Lite | `GEMINI_API_KEY` |

The offline preview remains available without credentials. Provider keys are read only by the API
container and are never returned to the dashboard or stored in prompt definitions.

## Local setup

Add only the keys you intend to use to the uncommitted `.env` file:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
```

Then rebuild the containers so the provider SDK and environment values are available:

```bash
docker compose up --build -d --force-recreate
```

Check configuration without printing secret values:

```bash
docker compose exec api sh -lc 'for name in OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY; do eval "value=\${$name}"; [ -n "$value" ] && echo "$name configured" || echo "$name missing"; done'
```

## Cost boundary

Displayed costs are estimates calculated from reported input and output tokens and the configured
model rates. Provider billing remains authoritative. A public deployment must not expose or share
the owner's provider credentials; user-supplied keys and authentication belong to a later hosted
BYOK phase.
