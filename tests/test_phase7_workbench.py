from fastapi.testclient import TestClient

from prompt_laboratory.api import create_app

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


def test_workbench_catalog_and_offline_execution(tmp_path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "greeting.yaml").write_text(PROMPT, encoding="utf-8")
    app = create_app(f"sqlite:///{tmp_path / 'runs.db'}", prompts)

    with TestClient(app) as client:
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
    app = create_app(f"sqlite:///{tmp_path / 'runs.db'}", prompts)

    with TestClient(app) as client:
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
