"""End-to-end smoke test for the Docker Compose stack."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from uuid import uuid4

API_URL = os.getenv("PROMPT_LAB_API_URL", "http://localhost:8000").rstrip("/")
DASHBOARD_URL = os.getenv("PROMPT_LAB_DASHBOARD_URL", "http://localhost:8501").rstrip("/")
TIMEOUT_SECONDS = int(os.getenv("PROMPT_LAB_SMOKE_TIMEOUT", "120"))


def request_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> object:
    body = json.dumps(payload).encode() if payload is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=body,
        headers=request_headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def assert_http_status(
    path: str,
    expected_status: int,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    try:
        request_json(path, method=method, payload=payload, headers=headers)
    except urllib.error.HTTPError as exc:
        assert exc.code == expected_status, (
            f"Expected HTTP {expected_status} for {method} {path}, got {exc.code}"
        )
        return
    raise AssertionError(f"Expected HTTP {expected_status} for {method} {path}")


def wait_until_ready(url: str, name: str) -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f"{name} did not become ready: {last_error}")


def main() -> None:
    wait_until_ready(f"{API_URL}/health", "API")
    wait_until_ready(f"{DASHBOARD_URL}/_stcore/health", "dashboard")

    email = f"compose-smoke-{uuid4().hex}@example.com"
    registered = request_json(
        "/api/v1/auth/register",
        method="POST",
        payload={
            "email": email,
            "display_name": "Compose Smoke Test",
            "password": "correct-horse-battery-staple",
            "workspace_name": "Compose Verification",
        },
    )
    assert isinstance(registered, dict)
    token = str(registered["access_token"])
    workspace_id = str(registered["workspaces"][0]["id"])
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": workspace_id,
    }

    collaborator_email = f"compose-collaborator-{uuid4().hex}@example.com"
    collaborator = request_json(
        "/api/v1/auth/register",
        method="POST",
        payload={
            "email": collaborator_email,
            "display_name": "Compose Collaborator",
            "password": "correct-horse-battery-staple",
            "workspace_name": "Collaborator Personal Workspace",
        },
    )
    assert isinstance(collaborator, dict)
    collaborator_token = str(collaborator["access_token"])
    collaborator_headers = {"Authorization": f"Bearer {collaborator_token}"}

    assert_http_status(
        f"/api/v1/workspaces/{workspace_id}/members",
        403,
        headers=collaborator_headers,
    )

    invitation = request_json(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        method="POST",
        payload={"email": collaborator_email, "role": "viewer"},
        headers=auth_headers,
    )
    assert isinstance(invitation, dict)
    invitation_token = str(invitation["token"])
    assert invitation["role"] == "viewer"

    accepted = request_json(
        "/api/v1/invitations/accept",
        method="POST",
        payload={"token": invitation_token},
        headers=collaborator_headers,
    )
    assert isinstance(accepted, dict)
    assert accepted["status"] == "accepted"

    collaborator_headers["X-Workspace-ID"] = workspace_id
    members = request_json(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=collaborator_headers,
    )
    assert isinstance(members, list)
    collaborator_member = next(
        member for member in members if member["email"] == collaborator_email
    )
    collaborator_user_id = str(collaborator_member["user_id"])
    assert collaborator_member["role"] == "viewer"

    identity = request_json("/api/v1/auth/me", headers=auth_headers)
    assert isinstance(identity, dict)
    assert identity["user"]["email"] == email

    credential = request_json(
        "/api/v1/credentials/openai",
        method="PUT",
        payload={"api_key": "compose-smoke-provider-key"},
        headers=auth_headers,
    )
    assert isinstance(credential, dict)
    assert credential["source"] == "user"
    assert "compose-smoke-provider-key" not in json.dumps(credential)

    credentials = request_json("/api/v1/credentials", headers=auth_headers)
    assert isinstance(credentials, list)
    openai_status = next(
        item for item in credentials if item["provider"] == "openai"
    )
    assert openai_status["source"] == "user"

    prompts = request_json("/api/v1/prompts", headers=auth_headers)
    assert isinstance(prompts, list) and prompts
    prompt = prompts[0]
    variables = {
        name: definition.get("default")
        for name, definition in prompt["variables"].items()
        if definition.get("default") is not None
    }
    for name, definition in prompt["variables"].items():
        if name not in variables:
            variable_type = definition["type"]
            variables[name] = {
                "string": "smoke test",
                "integer": 1,
                "number": 1.0,
                "boolean": False,
                "object": {},
                "array": [],
            }[variable_type]

    assert_http_status(
        "/api/v1/workbench/execute",
        403,
        method="POST",
        payload={
            "prompt_id": prompt["id"],
            "variables": variables,
            "provider": "mock/echo",
        },
        headers=collaborator_headers,
    )

    promoted = request_json(
        f"/api/v1/workspaces/{workspace_id}/members/{collaborator_user_id}",
        method="PATCH",
        payload={"role": "editor"},
        headers=auth_headers,
    )
    assert isinstance(promoted, dict)
    assert promoted["role"] == "editor"

    collaborator_result = request_json(
        "/api/v1/workbench/execute",
        method="POST",
        payload={
            "prompt_id": prompt["id"],
            "variables": variables,
            "provider": "mock/echo",
        },
        headers=collaborator_headers,
    )
    assert isinstance(collaborator_result, dict)
    assert collaborator_result["provider"] == "mock"

    result = request_json(
        "/api/v1/workbench/execute",
        method="POST",
        payload={
            "prompt_id": prompt["id"],
            "variables": variables,
            "provider": "mock/echo",
        },
        headers=auth_headers,
    )
    assert isinstance(result, dict)
    assert result["provider"] == "mock"
    assert result["output"]
    experiment_id = str(result["experiment_id"])

    experiment = request_json(
        f"/api/v1/experiments/{experiment_id}", headers=auth_headers
    )
    assert isinstance(experiment, dict)
    assert experiment["workspace_id"] == workspace_id
    assert experiment["mode"] == "single"

    runs = request_json("/api/v1/runs", headers=auth_headers)
    assert runs == []
    print("Docker Compose smoke test passed.")


if __name__ == "__main__":
    main()
