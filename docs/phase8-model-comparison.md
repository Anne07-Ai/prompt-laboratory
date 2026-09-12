# Phase 8 — Model comparison workbench

Phase 8 turns the interactive workbench into a provider comparison surface.

## Capabilities

- run the same rendered prompt across multiple configured providers
- execute independent provider requests concurrently
- compare output, latency, token usage, and estimated cost side by side
- preserve successful results when one provider fails
- return safe quota, rate-limit, and authentication errors without exposing credentials
- retain single-model execution for focused prompt development

The workbench currently provides verified cost estimation for GPT-4.1 mini. A zero value for
other providers means pricing is not configured, not that provider usage is necessarily free.

## API

`POST /api/v1/workbench/compare`

```json
{
  "prompt_id": "education.level-adapted-explanation",
  "variables": {
    "concept": "Artificial Intelligence",
    "learning_level": "Beginner"
  },
  "providers": ["mock/echo", "openai/gpt-4.1-mini"]
}
```

Every comparison item contains either a provider result or a safe error object, allowing the
dashboard to render partial comparisons instead of failing the entire experiment.
