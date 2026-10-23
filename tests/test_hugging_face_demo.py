import os

from fastapi.testclient import TestClient

from prompt_laboratory.api import create_app
from scripts.run_hugging_face import configure_environment

TEST_SECRET = "hugging-face-demo-secret-that-is-long-enough"
TEST_CREDENTIAL_KEY = "hugging-face-credential-key-that-is-long-enough"


def demo_client(tmp_path) -> TestClient:
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'demo.db'}",
        prompts_dir="prompts",
        auth_secret=TEST_SECRET,
        credential_key=TEST_CREDENTIAL_KEY,
        demo_mode=True,
    )
    return TestClient(app)


def register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "demo@example.invalid",
            "display_name": "Demo visitor",
            "password": "generated-demo-password",
            "workspace_name": "Public demo workspace",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Workspace-ID": payload["workspaces"][0]["id"],
    }


def test_demo_mode_exposes_only_mock_provider(tmp_path) -> None:
    with demo_client(tmp_path) as client:
        client.headers.update(register(client))
        assert client.get("/api/v1/providers").json() == [
            {"id": "mock/echo", "label": "Offline preview", "configured": True}
        ]

        response = client.post(
            "/api/v1/workbench/execute",
            json={
                "prompt_id": "education.concept-explanation",
                "variables": {"concept": "gravity", "learning_level": "beginner"},
                "provider": "mock/echo",
            },
        )
        assert response.status_code == 200
        assert response.json()["provider"] == "mock"


def test_demo_mode_rejects_live_providers_and_credentials(tmp_path) -> None:
    with demo_client(tmp_path) as client:
        client.headers.update(register(client))

        execute = client.post(
            "/api/v1/workbench/execute",
            json={
                "prompt_id": "education.concept-explanation",
                "variables": {"concept": "gravity", "learning_level": "beginner"},
                "provider": "openai/gpt-4.1-mini",
            },
        )
        assert execute.status_code == 403

        comparison = client.post(
            "/api/v1/workbench/compare",
            json={
                "prompt_id": "education.concept-explanation",
                "variables": {"concept": "gravity", "learning_level": "beginner"},
                "providers": ["mock/echo", "openai/gpt-4.1-mini"],
            },
        )
        assert comparison.status_code == 403

        assert client.get("/api/v1/credentials").status_code == 403
        assert client.put(
            "/api/v1/credentials/openai", json={"api_key": "must-not-be-stored"}
        ).status_code == 403
        assert client.delete("/api/v1/credentials/openai").status_code == 403


def test_hugging_face_runtime_removes_live_provider_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_LAB_HF_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PROMPT_LAB_DEMO_MODE", "false")
    monkeypatch.setenv("PROMPT_LAB_AUTH_SECRET", "too-short")
    monkeypatch.setenv("PROMPT_LAB_CREDENTIAL_KEY", "too-short")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")

    configure_environment()

    assert not any(
        key in os.environ
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
    )
    assert os.environ["PROMPT_LAB_DEMO_MODE"] == "true"
    assert len(os.environ["PROMPT_LAB_AUTH_SECRET"]) >= 32
    assert len(os.environ["PROMPT_LAB_CREDENTIAL_KEY"]) >= 32
