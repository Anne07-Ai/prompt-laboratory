from fastapi.testclient import TestClient

from prompt_laboratory.api import create_app
from prompt_laboratory.credentials import CredentialCipher
from prompt_laboratory.providers.base import ProviderResponse

AUTH_SECRET = "phase-9b-auth-secret-that-is-long-enough"
CREDENTIAL_KEY = "phase-9b-credential-key-that-is-long-enough"


def register(client: TestClient, email: str) -> tuple[dict[str, str], dict[str, object]]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Credential Owner",
            "password": "correct-horse-battery-staple",
            "workspace_name": "Credential Lab",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return (
        {
            "Authorization": f"Bearer {payload['access_token']}",
            "X-Workspace-ID": payload["workspaces"][0]["id"],
        },
        payload,
    )


def test_cipher_binds_ciphertext_to_user_and_provider() -> None:
    cipher = CredentialCipher(CREDENTIAL_KEY)
    encrypted = cipher.encrypt(
        "secret-provider-key",
        user_id="user-one",
        provider="openai",
    )
    assert "secret-provider-key" not in encrypted
    assert (
        cipher.decrypt(encrypted, user_id="user-one", provider="openai")
        == "secret-provider-key"
    )

    for user_id, provider in [
        ("user-two", "openai"),
        ("user-one", "anthropic"),
    ]:
        try:
            cipher.decrypt(encrypted, user_id=user_id, provider=provider)
        except ValueError as exc:
            assert str(exc) == "Stored provider credential cannot be decrypted"
        else:
            raise AssertionError("Credential identity binding was bypassed")


def test_credential_lifecycle_is_masked_and_user_isolated(tmp_path, monkeypatch) -> None:
    for variable in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(variable, raising=False)

    app = create_app(
        f"sqlite:///{tmp_path / 'credentials.db'}",
        auth_secret=AUTH_SECRET,
        credential_key=CREDENTIAL_KEY,
    )
    with TestClient(app) as client:
        owner_headers, owner = register(client, "owner@example.com")
        api_key = "sk-user-secret-that-must-never-be-returned"
        saved = client.put(
            "/api/v1/credentials/openai",
            headers=owner_headers,
            json={"api_key": api_key},
        )
        assert saved.status_code == 200
        assert saved.json()["source"] == "user"
        assert api_key not in saved.text

        user_id = str(owner["user"]["id"])
        encrypted = app.state.store.get_provider_credential(user_id, "openai")
        assert encrypted is not None
        assert api_key not in encrypted

        statuses = client.get("/api/v1/credentials", headers=owner_headers)
        assert statuses.status_code == 200
        assert api_key not in statuses.text
        openai = next(
            item for item in statuses.json() if item["provider"] == "openai"
        )
        assert openai["configured"] is True
        assert openai["source"] == "user"

        other_headers, _ = register(client, "other@example.com")
        other_statuses = client.get("/api/v1/credentials", headers=other_headers)
        other_openai = next(
            item for item in other_statuses.json() if item["provider"] == "openai"
        )
        assert other_openai["configured"] is False
        assert other_openai["source"] == "unconfigured"

        deleted = client.delete(
            "/api/v1/credentials/openai",
            headers=owner_headers,
        )
        assert deleted.status_code == 204
        assert app.state.store.get_provider_credential(user_id, "openai") is None


def test_user_credential_is_decrypted_only_for_provider_execution(
    tmp_path, monkeypatch
) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "greeting.yaml").write_text(
        """\
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
""",
        encoding="utf-8",
    )
    app = create_app(
        f"sqlite:///{tmp_path / 'execution.db'}",
        prompts,
        AUTH_SECRET,
        CREDENTIAL_KEY,
    )
    captured: dict[str, str] = {}

    def fake_execute(prompt, variables, provider_id, api_keys):
        captured.update(api_keys)
        return "Hello Lakshmi", ProviderResponse(
            text="Hello from OpenAI",
            provider="openai",
            model="gpt-4.1-mini",
            latency_ms=1,
            input_tokens=2,
            output_tokens=3,
        )

    monkeypatch.setattr("prompt_laboratory.api.execute_prompt", fake_execute)

    with TestClient(app) as client:
        headers, _ = register(client, "runner@example.com")
        api_key = "sk-runtime-user-key"
        assert (
            client.put(
                "/api/v1/credentials/openai",
                headers=headers,
                json={"api_key": api_key},
            ).status_code
            == 200
        )
        response = client.post(
            "/api/v1/workbench/execute",
            headers=headers,
            json={
                "prompt_id": "demo.greeting",
                "variables": {"name": "Lakshmi"},
                "provider": "openai/gpt-4.1-mini",
            },
        )
        assert response.status_code == 200
        assert captured == {"openai": api_key}
        assert api_key not in response.text
