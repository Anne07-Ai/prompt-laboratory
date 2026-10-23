# Hugging Face public demonstration

The Hugging Face Space is a public product demonstration, not a production deployment. GitHub
remains the engineering source of truth.

## Runtime architecture

The Docker Space runs two processes inside one container:

- Streamlit is the only public service and listens on port `7860`.
- FastAPI listens only on `127.0.0.1:8000` and is reachable by the dashboard inside the container.
- SQLite stores temporary demonstration state and may be reset whenever the Space restarts.

`scripts/run_hugging_face.py` supervises both processes and generates unique runtime authentication
and credential-encryption secrets when the container starts. Secrets and provider keys are never
committed to the repository.

## Public-demo security boundary

`PROMPT_LAB_DEMO_MODE=true` enforces the public boundary in both the API and dashboard:

- visitors receive isolated, randomly generated demo identities without entering personal details
- only the deterministic `mock/echo` provider is listed or executable
- live-provider comparison is disabled
- provider credential listing, storage, rotation, and deletion are rejected by the API
- OpenAI, Anthropic, and Gemini environment keys are removed before services start
- a visible notice prohibits personal, confidential, regulated, and production information

The restrictions are enforced server-side. Hiding controls in Streamlit is only a usability measure.

## Local verification

```bash
docker build -f Dockerfile.huggingface -t prompt-laboratory-hf .
docker run --rm -p 7860:7860 prompt-laboratory-hf
```

Open <http://localhost:7860>. No provider API keys are required or accepted.

## Space configuration

Create the Space with the Docker SDK and free CPU hardware. In the Space repository, use
`Dockerfile.huggingface` as the root `Dockerfile`, retain the full application source, and include
this metadata in the Space `README.md`:

```yaml
---
title: Prompt Laboratory
emoji: 🧪
colorFrom: purple
colorTo: cyan
sdk: docker
app_port: 7860
license: apache-2.0
---
```

Do not configure provider API keys as Space secrets. The public Space is intentionally mock-only.
