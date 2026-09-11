from datetime import UTC, datetime

from fastapi.testclient import TestClient

from prompt_laboratory.api import create_app
from prompt_laboratory.evaluation import EvaluationReport, RunSummary


def sample_report() -> dict[str, object]:
    return EvaluationReport(
        created_at=datetime.now(UTC),
        prompt_id="education.concept-explanation",
        prompt_version="1.0.0",
        provider="mock/local-deterministic",
        summary=RunSummary(
            total_cases=2,
            passed_cases=2,
            failed_cases=0,
            pass_rate=1,
            average_score=0.98,
            total_latency_ms=15,
            input_tokens=20,
            output_tokens=10,
            estimated_cost_usd=0,
        ),
        cases=[],
    ).model_dump(mode="json")


def test_health_and_run_lifecycle(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'runs.db'}")
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        created = client.post("/api/v1/runs", json=sample_report())
        assert created.status_code == 201
        run_id = created.json()["id"]

        listing = client.get("/api/v1/runs").json()
        assert listing[0]["id"] == run_id
        assert listing[0]["average_score"] == 0.98

        detail = client.get(f"/api/v1/runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["prompt_id"] == "education.concept-explanation"


def test_missing_run_is_404(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'runs.db'}")
    with TestClient(app) as client:
        response = client.get("/api/v1/runs/missing")
        assert response.status_code == 404
