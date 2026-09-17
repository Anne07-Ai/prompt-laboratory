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

    identity = request_json("/api/v1/auth/me", headers=auth_headers)
    assert isinstance(identity, dict)
    assert identity["user"]["email"] == email

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

    runs = request_json("/api/v1/runs", headers=auth_headers)
    assert runs == []
    print("Docker Compose smoke test passed.")


if __name__ == "__main__":
    main()
