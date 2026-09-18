from fastapi.testclient import TestClient

from prompt_laboratory.api import create_app

AUTH_SECRET = "phase-9c-member-auth-secret-that-is-long-enough"

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


def register(client: TestClient, email: str, workspace: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": email.split("@")[0].title(),
            "password": "correct-horse-battery-staple",
            "workspace_name": workspace,
        },
    )
    assert response.status_code == 201
    return response.json()


def auth(payload: dict[str, object], workspace_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    if workspace_id is not None:
        headers["X-Workspace-ID"] = workspace_id
    return headers


def invite_and_accept(
    client: TestClient,
    owner: dict[str, object],
    recipient: dict[str, object],
    workspace_id: str,
    role: str,
) -> None:
    email = str(recipient["user"]["email"])
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        headers=auth(owner),
        json={"email": email, "role": role},
    )
    assert created.status_code == 201
    accepted = client.post(
        "/api/v1/invitations/accept",
        headers=auth(recipient),
        json={"token": created.json()["token"]},
    )
    assert accepted.status_code == 200


def test_member_roles_and_final_owner_are_protected(tmp_path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "greeting.yaml").write_text(PROMPT, encoding="utf-8")
    app = create_app(
        f"sqlite:///{tmp_path / 'members.db'}",
        prompts,
        AUTH_SECRET,
    )
    with TestClient(app) as client:
        owner = register(client, "owner@example.com", "Shared Lab")
        admin = register(client, "admin@example.com", "Admin Lab")
        viewer = register(client, "viewer@example.com", "Viewer Lab")
        workspace_id = str(owner["workspaces"][0]["id"])
        owner_id = str(owner["user"]["id"])
        admin_id = str(admin["user"]["id"])
        viewer_id = str(viewer["user"]["id"])

        invite_and_accept(client, owner, admin, workspace_id, "admin")
        invite_and_accept(client, owner, viewer, workspace_id, "viewer")

        denied_run = client.post(
            "/api/v1/workbench/execute",
            headers=auth(viewer, workspace_id),
            json={
                "prompt_id": "demo.greeting",
                "variables": {"name": "Lakshmi"},
                "provider": "mock/echo",
            },
        )
        assert denied_run.status_code == 403

        promoted = client.patch(
            f"/api/v1/workspaces/{workspace_id}/members/{viewer_id}",
            headers=auth(admin),
            json={"role": "editor"},
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "editor"

        allowed_run = client.post(
            "/api/v1/workbench/execute",
            headers=auth(viewer, workspace_id),
            json={
                "prompt_id": "demo.greeting",
                "variables": {"name": "Lakshmi"},
                "provider": "mock/echo",
            },
        )
        assert allowed_run.status_code == 200

        admin_cannot_change_owner = client.patch(
            f"/api/v1/workspaces/{workspace_id}/members/{owner_id}",
            headers=auth(admin),
            json={"role": "viewer"},
        )
        assert admin_cannot_change_owner.status_code == 403

        editor_cannot_manage = client.delete(
            f"/api/v1/workspaces/{workspace_id}/members/{admin_id}",
            headers=auth(viewer),
        )
        assert editor_cannot_manage.status_code == 403

        final_owner = client.delete(
            f"/api/v1/workspaces/{workspace_id}/members/{owner_id}",
            headers=auth(owner),
        )
        assert final_owner.status_code == 409
        assert "final workspace owner" in final_owner.json()["detail"]

        removed = client.delete(
            f"/api/v1/workspaces/{workspace_id}/members/{admin_id}",
            headers=auth(owner),
        )
        assert removed.status_code == 204
        assert workspace_id not in {
            item["id"]
            for item in client.get("/api/v1/workspaces", headers=auth(admin)).json()
        }


def test_owner_role_cannot_be_assigned_by_member_update(tmp_path) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'owner-role.db'}",
        auth_secret=AUTH_SECRET,
    )
    with TestClient(app) as client:
        owner = register(client, "owner@example.com", "Shared Lab")
        viewer = register(client, "viewer@example.com", "Viewer Lab")
        workspace_id = str(owner["workspaces"][0]["id"])
        viewer_id = str(viewer["user"]["id"])
        invite_and_accept(client, owner, viewer, workspace_id, "viewer")

        response = client.patch(
            f"/api/v1/workspaces/{workspace_id}/members/{viewer_id}",
            headers=auth(owner),
            json={"role": "owner"},
        )
        assert response.status_code == 422
        assert "Owner transfer" in response.json()["detail"]
