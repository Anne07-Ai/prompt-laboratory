"""Interactive prompt discovery, rendering, and provider execution."""

import os
from pathlib import Path
from typing import Any

from prompt_laboratory.loader import load_prompt
from prompt_laboratory.models import PromptDefinition
from prompt_laboratory.providers import AnthropicProvider, OpenAIProvider
from prompt_laboratory.providers.base import ProviderRequest, ProviderResponse
from prompt_laboratory.renderer import PromptRenderer


class PromptCatalog:
    """Read-only catalog backed by Git-versioned YAML prompt files."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def all(self) -> list[PromptDefinition]:
        return sorted(
            (load_prompt(path) for path in self.root.rglob("*.yaml")),
            key=lambda prompt: (prompt.industry, prompt.name, prompt.version),
        )

    def get(self, prompt_id: str) -> PromptDefinition | None:
        return next((prompt for prompt in self.all() if prompt.id == prompt_id), None)


class EchoProvider:
    """Offline provider that makes the workbench usable without API credentials."""

    @property
    def name(self) -> str:
        return "mock/echo"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        text = f"[Offline preview]\n{request.prompt}"
        return ProviderResponse(
            text=text,
            provider="mock",
            model="echo",
            latency_ms=0,
            input_tokens=len(request.prompt.split()),
            output_tokens=len(text.split()),
        )


def provider_options() -> list[dict[str, Any]]:
    """Return safe provider metadata; never expose credential values."""
    return [
        {"id": "mock/echo", "label": "Offline preview", "configured": True},
        {
            "id": "openai/gpt-4.1-mini",
            "label": "OpenAI · GPT-4.1 mini",
            "configured": bool(os.getenv("OPENAI_API_KEY")),
        },
        {
            "id": "anthropic/claude-3-5-haiku-latest",
            "label": "Anthropic · Claude 3.5 Haiku",
            "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        },
    ]


def execute_prompt(
    prompt: PromptDefinition,
    values: dict[str, Any],
    provider_id: str,
) -> tuple[str, ProviderResponse]:
    rendered = PromptRenderer().render(prompt, values)
    if provider_id == "mock/echo":
        provider = EchoProvider()
    elif provider_id.startswith("openai/"):
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not configured")
        provider = OpenAIProvider(provider_id.removeprefix("openai/"))
    elif provider_id.startswith("anthropic/"):
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        provider = AnthropicProvider(provider_id.removeprefix("anthropic/"))
    else:
        raise ValueError(f"Unsupported provider: {provider_id}")

    response = provider.generate(
        ProviderRequest(case_id="interactive-workbench", prompt=rendered)
    )
    return rendered, response
