# Demonstration guide

## 90-second story

1. Open a versioned healthcare prompt and its YAML test dataset.
2. Explain that every prompt change is evaluated by deterministic checks and optional LLM judges.
3. Show the GitHub quality gate blocking score or pass-rate regressions.
4. Open the experiment console and compare quality, latency, and cost across versions.
5. Finish with the approved version and its auditable evaluation record.

## Start the stack

```bash
docker compose up --build -d
```

## Add a three-version demonstration

Run the seeder inside the API container, where `httpx` is already installed:

```bash
docker compose exec api python scripts/seed_demo_runs.py
```

The API image must include the `scripts` directory. Rebuild after pulling the Phase 6 release.

Open <http://localhost:8501> and use the prompt/provider filters to explain the trajectory.

## Capture portfolio screenshots

- Full experiment overview at 1440 px or wider
- Release signal and five KPI cards
- Quality trajectory plus latest-run gauge
- Run-history tab
- FastAPI `/docs` page
- Successful GitHub Actions quality gate

Never include API keys, environment variables, private datasets, browser bookmarks, or unrelated
applications in screenshots.
