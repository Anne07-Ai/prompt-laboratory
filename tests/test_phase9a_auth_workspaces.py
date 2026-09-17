from fastapi.testclient import TestClient

from prompt_laboratory.api import create_app

TEST_SECRET = "phase-9a-test-secret-that-is-long-enough"


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


def test_registration_login_and_identity(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'auth.db'}", auth_secret=TEST_SECRET)
    with TestClient(app) as client:
        registered = register(client, "lakshmi@example.com", "Lakshmi Lab")
        headers = {"Authorization": f"Bearer {registered['access_token']}"}

        identity = client.get("/api/v1/auth/me", headers=headers)
        assert identity.status_code == 200
        assert identity.json()["user"]["email"] == "lakshmi@example.com"
        assert identity.json()["workspaces"][0]["role"] == "owner"

        logged_in = client.post(
            "/api/v1/auth/login",
            json={
                "email": "LAKSHMI@example.com",
                "password": "correct-horse-battery-staple",
            },
        )
        assert logged_in.status_code == 200
        assert logged_in.json()["token_type"] == "bearer"


def test_duplicate_account_and_invalid_password_are_rejected(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'auth.db'}", auth_secret=TEST_SECRET)
    with TestClient(app) as client:
        register(client, "owner@example.com", "Owner Lab")
        duplicate = client.post(
            "/api/v1/auth/register",
            json={
                "email": "owner@example.com",
                "display_name": "Another owner",
                "password": "another-secure-password",
                "workspace_name": "Another Lab",
            },
        )
        assert duplicate.status_code == 409

        invalid = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "wrong-password"},
        )
        assert invalid.status_code == 401


def test_workspace_membership_is_enforced(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'auth.db'}", auth_secret=TEST_SECRET)
    with TestClient(app) as client:
        first = register(client, "first@example.com", "First Lab")
        second = register(client, "second@example.com", "Second Lab")

        first_headers = {
            "Authorization": f"Bearer {first['access_token']}",
            "X-Workspace-ID": first["workspaces"][0]["id"],
        }
        forbidden_headers = {
            "Authorization": f"Bearer {second['access_token']}",
            "X-Workspace-ID": first["workspaces"][0]["id"],
        }

        assert client.get("/api/v1/runs", headers=first_headers).status_code == 200
        assert client.get("/api/v1/runs", headers=forbidden_headers).status_code == 403
        assert client.get("/api/v1/runs").status_code == 401


def test_user_can_create_another_workspace(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'auth.db'}", auth_secret=TEST_SECRET)
    with TestClient(app) as client:
        registered = register(client, "owner@example.com", "First Lab")
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        created = client.post(
            "/api/v1/workspaces",
            json={"name": "Research Lab"},
            headers=headers,
        )
        assert created.status_code == 201
        assert created.json()["role"] == "owner"
        assert len(client.get("/api/v1/workspaces", headers=headers).json()) == 2
