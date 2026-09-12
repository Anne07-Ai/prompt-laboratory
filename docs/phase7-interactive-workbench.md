# Phase 7 — Interactive Prompt Workbench

Phase 7 turns the experiment console from a read-only results view into an interactive prompt
engineering surface.

## Delivered

- API-backed discovery of every Git-versioned YAML prompt contract
- dynamic form controls generated from typed prompt variables
- strict Jinja2 rendering through the existing validation layer
- an offline preview provider that works without credentials
- optional OpenAI and Anthropic execution when server-side keys are configured
- rendered-prompt, output, latency and token inspection

## Architecture decision

Provider credentials remain on the API service. The browser receives only provider availability
metadata and never receives secret values. Prompt files remain the source of truth; the workbench
does not silently mutate YAML or bypass Git review.

The offline provider is intentionally labelled as a preview. It verifies template and UI behaviour
but is not presented as a quality evaluation or a substitute for a language model.

## Local use

The workbench is available at `http://localhost:8501` after starting Docker Compose. To enable a
live provider, export a key before starting the stack:

```bash
export OPENAI_API_KEY="..."
docker compose up --build -d
```

Use secret management rather than committing keys to this repository.
