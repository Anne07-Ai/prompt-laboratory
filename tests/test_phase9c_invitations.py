from fastapi.testclient import TestClient
from sqlalchemy import text

from prompt_laboratory.api import create_app

AUTH_SECRET = "phase-9c-invitation-secret-that-is-long-enough"


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


def auth(payload: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_owner_can_invite_and_recipient_can_accept_once(tmp_path) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'invitations.db'}",
        auth_secret=AUTH_SECRET,
    )
    with TestClient(app) as client:
        owner = register(client, "owner@example.com", "Shared Lab")
        invited = register(client, "editor@example.com", "Personal Lab")
        workspace_id = str(owner["workspaces"][0]["id"])

        created = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers=auth(owner),
            json={"email": "EDITOR@example.com", "role": "editor"},
        )
        assert created.status_code == 201
        token = created.json()["token"]
        assert created.json()["invited_email"] == "editor@example.com"
        assert created.json()["role"] == "editor"

        with app.state.store.engine.connect() as connection:
            stored_hash = connection.execute(
                text("SELECT token_hash FROM workspace_invitations")
            ).scalar_one()
        assert token not in stored_hash

        owner_list = client.get(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers=auth(owner),
        )
        assert owner_list.status_code == 200
        assert "token" not in owner_list.text
        assert owner_list.json()[0]["status"] == "pending"

        recipient_list = client.get("/api/v1/invitations", headers=auth(invited))
        assert recipient_list.status_code == 200
        assert recipient_list.json()[0]["workspace_name"] == "Shared Lab"

        accepted = client.post(
            "/api/v1/invitations/accept",
            headers=auth(invited),
            json={"token": token},
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "accepted"

        workspaces = client.get("/api/v1/workspaces", headers=auth(invited)).json()
        shared = next(item for item in workspaces if item["id"] == workspace_id)
        assert shared["role"] == "editor"

        members = client.get(
            f"/api/v1/workspaces/{workspace_id}/members",
            headers=auth(invited),
        )
        assert members.status_code == 200
        assert {member["email"] for member in members.json()} == {
            "owner@example.com",
            "editor@example.com",
        }

        reused = client.post(
            "/api/v1/invitations/accept",
            headers=auth(invited),
            json={"token": token},
        )
        assert reused.status_code == 409


def test_invitation_is_email_bound_and_can_be_rejected(tmp_path) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'email-bound.db'}",
        auth_secret=AUTH_SECRET,
    )
    with TestClient(app) as client:
        owner = register(client, "owner@example.com", "Shared Lab")
        invited = register(client, "viewer@example.com", "Viewer Lab")
        attacker = register(client, "attacker@example.com", "Attacker Lab")
        workspace_id = str(owner["workspaces"][0]["id"])

        created = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers=auth(owner),
            json={"email": "viewer@example.com", "role": "viewer"},
        )
        token = created.json()["token"]

        wrong_user = client.post(
            "/api/v1/invitations/accept",
            headers=auth(attacker),
            json={"token": token},
        )
        assert wrong_user.status_code == 409
        assert workspace_id not in {
            item["id"]
            for item in client.get("/api/v1/workspaces", headers=auth(attacker)).json()
        }

        rejected = client.post(
            "/api/v1/invitations/reject",
            headers=auth(invited),
            json={"token": token},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert client.get("/api/v1/invitations", headers=auth(invited)).json() == []


def test_invitation_creation_enforces_manage_members(tmp_path) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'permissions.db'}",
        auth_secret=AUTH_SECRET,
    )
    with TestClient(app) as client:
        owner = register(client, "owner@example.com", "Shared Lab")
        viewer = register(client, "viewer@example.com", "Viewer Lab")
        workspace_id = str(owner["workspaces"][0]["id"])

        invitation = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers=auth(owner),
            json={"email": "viewer@example.com", "role": "viewer"},
        )
        token = invitation.json()["token"]
        assert client.post(
            "/api/v1/invitations/accept",
            headers=auth(viewer),
            json={"token": token},
        ).status_code == 200

        forbidden = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers=auth(viewer),
            json={"email": "another@example.com", "role": "editor"},
        )
        assert forbidden.status_code == 403

        owner_role = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers=auth(owner),
            json={"email": "another@example.com", "role": "owner"},
        )
        assert owner_role.status_code == 422
