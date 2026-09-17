from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from prompt_laboratory.api import create_app

TEST_SECRET = "experiment-persistence-test-secret-long-enough"

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


def register(client: TestClient, email: str = "owner@example.com") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Experiment Owner",
            "password": "correct-horse-battery-staple",
            "workspace_name": "Experiment Lab",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Workspace-ID": payload["workspaces"][0]["id"],
    }


def test_single_workbench_run_is_persisted_and_workspace_scoped(tmp_path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "greeting.yaml").write_text(PROMPT, encoding="utf-8")
    app = create_app(f"sqlite:///{tmp_path / 'experiments.db'}", prompts, TEST_SECRET)

    with TestClient(app) as client:
        owner_headers = register(client)
        response = client.post(
            "/api/v1/workbench/execute",
            headers=owner_headers,
            json={
                "prompt_id": "demo.greeting",
                "variables": {"name": "Lakshmi"},
                "provider": "mock/echo",
            },
        )
        assert response.status_code == 200
        experiment_id = response.json()["experiment_id"]

        history = client.get("/api/v1/experiments", headers=owner_headers)
        assert history.status_code == 200
        assert history.json()[0]["id"] == experiment_id
        assert history.json()[0]["mode"] == "single"

        experiment = client.get(
            f"/api/v1/experiments/{experiment_id}", headers=owner_headers
        )
        assert experiment.status_code == 200
        assert experiment.json()["rendered_prompt"] == "Hello Lakshmi"
        assert "Hello Lakshmi" in experiment.json()["result"]["output"]

        other_headers = register(client, "other@example.com")
        hidden = client.get(
            f"/api/v1/experiments/{experiment_id}", headers=other_headers
        )
        assert hidden.status_code == 404


def test_existing_baseline_schema_upgrades_to_experiments(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0001")

    app = create_app(database_url, auth_secret=TEST_SECRET)
    with TestClient(app) as client:
        headers = register(client, "upgrade@example.com")
        assert client.get("/api/v1/experiments", headers=headers).json() == []

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    assert command.current(config) is None
