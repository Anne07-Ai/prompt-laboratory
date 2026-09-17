# Phase 9B — Encrypted provider credentials

Phase 9B lets each authenticated user configure OpenAI, Anthropic, and Gemini without exposing
provider keys to the browser after submission or storing plaintext credentials in the database.

## Trust boundary

- The API accepts a credential only over an authenticated write endpoint.
- AES-256-GCM encrypts the value before persistence.
- Associated data binds ciphertext to the owning user and provider, preventing record swapping.
- A separate `PROMPT_LAB_CREDENTIAL_KEY` protects provider credentials.
- Credential values never appear in list responses, experiment records, logs, or dashboard state.
- User credentials take precedence for that user's execution only.
- Deployment environment keys remain an optional fallback.

## Lifecycle

Users can add, rotate, or remove personal keys from the dashboard. Rotation replaces the encrypted
value in place. Status responses expose only provider name, source, and update time.

## API

- `GET /api/v1/credentials`
- `PUT /api/v1/credentials/{provider}`
- `DELETE /api/v1/credentials/{provider}`

Supported provider names are `openai`, `anthropic`, and `gemini`.
