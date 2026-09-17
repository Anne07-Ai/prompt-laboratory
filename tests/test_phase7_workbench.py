from fastapi.testclient import TestClient

from prompt_laboratory.api import create_app
from prompt_laboratory.providers.base import ProviderResponse
from prompt_laboratory.workbench import PromptCatalog, ProviderExecutionError, compare_prompt

TEST_SECRET = "phase-9a-test-secret-that-is-long-enough"

PROMPT = """\
schema_version: "1.0"
id: demo.greeting
version: "1.0.0"
name: Greeting
description: Create a greeting
industry: general
task: generation
owners: [team@example.com]
template: "Hello {{ name }}"
variables:
  name:
    type: string
    description: Person name
output:
  type: text
  description: A greeting
"""


def register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "workbench@example.com",
            "display_name": "Workbench Owner",
            "password": "correct-horse-battery-staple",
            "workspace_name": "Workbench",
        },
    )
    payload = response.json()
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Workspace-ID": payload["workspaces"][0]["id"],
    }


def test_workbench_catalog_and_offline_execution(tmp_path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "greeting.yaml").write_text(PROMPT, encoding="utf-8")
    app = create_app(f"sqlite:///{tmp_path / 'runs.db'}", prompts, TEST_SECRET)

    with TestClient(app) as client:
        client.headers.update(register(client))
        catalog = client.get("/api/v1/prompts")
        assert catalog.status_code == 200
        assert catalog.json()[0]["id"] == "demo.greeting"

        providers = client.get("/api/v1/providers").json()
        assert providers[0] == {
            "id": "mock/echo",
            "label": "Offline preview",
            "configured": True,
        }

        response = client.post(
            "/api/v1/workbench/execute",
            json={
                "prompt_id": "demo.greeting",
                "variables": {"name": "Lakshmi"},
                "provider": "mock/echo",
            },
        )
        assert response.status_code == 200
        assert response.json()["rendered_prompt"] == "Hello Lakshmi"
        assert "Hello Lakshmi" in response.json()["output"]


def test_workbench_rejects_invalid_input_and_unknown_prompt(tmp_path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "greeting.yaml").write_text(PROMPT, encoding="utf-8")
    app = create_app(f"sqlite:///{tmp_path / 'runs.db'}", prompts, TEST_SECRET)

    with TestClient(app) as client:
        client.headers.update(register(client))
        missing = client.post(
            "/api/v1/workbench/execute",
            json={"prompt_id": "missing", "variables": {}, "provider": "mock/echo"},
        )
        assert missing.status_code == 404

        invalid = client.post(
            "/api/v1/workbench/execute",
            json={"prompt_id": "demo.greeting", "variables": {}, "provider": "mock/echo"},
        )
        assert invalid.status_code == 422
        assert invalid.json()["detail"] == "Missing required variable: name"

        empty = client.post(
            "/api/v1/workbench/execute",
            json={
                "prompt_id": "demo.greeting",
                "variables": {"name": "   "},
                "provider": "mock/echo",
            },
        )
        assert empty.status_code == 422
        assert empty.json()["detail"] == "Variable 'name' cannot be empty"


def test_workbench_compares_multiple_providers(tmp_path, monkeypatch) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "greeting.yaml").write_text(PROMPT, encoding="utf-8")
    prompt = PromptCatalog(prompts).get("demo.greeting")
    assert prompt is not None

    def fake_execute(prompt, values, provider_id):
        rendered = f"Hello {values['name']}"
        return rendered, ProviderResponse(
            text=f"Response from {provider_id}",
            provider=provider_id.split("/")[0],
            model=provider_id.split("/")[1],
            latency_ms=12,
            input_tokens=2,
            output_tokens=4,
        )

    monkeypatch.setattr("prompt_laboratory.workbench.execute_prompt", fake_execute)
    rendered, comparisons = compare_prompt(
        prompt,
        {"name": "Lakshmi"},
        ["mock/one", "mock/two"],
    )
    assert rendered == "Hello Lakshmi"
    assert [item["provider_id"] for item in comparisons] == ["mock/one", "mock/two"]
    assert all(item["error"] is None for item in comparisons)


def test_workbench_returns_safe_provider_error(tmp_path, monkeypatch) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "greeting.yaml").write_text(PROMPT, encoding="utf-8")
    app = create_app(f"sqlite:///{tmp_path / 'runs.db'}", prompts, TEST_SECRET)

    def fail(*_args, **_kwargs):
        raise ProviderExecutionError(
            "openai/gpt-4.1-mini",
            "This provider has no API credit remaining. Add credit and try again.",
            "quota_exceeded",
        )

    monkeypatch.setattr("prompt_laboratory.api.execute_prompt", fail)
    with TestClient(app) as client:
        client.headers.update(register(client))
        response = client.post(
            "/api/v1/workbench/execute",
            json={
                "prompt_id": "demo.greeting",
                "variables": {"name": "Lakshmi"},
                "provider": "openai/gpt-4.1-mini",
            },
        )
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "quota_exceeded"
