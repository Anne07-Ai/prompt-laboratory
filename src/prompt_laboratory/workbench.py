"""Interactive prompt discovery, rendering, and provider execution."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from prompt_laboratory.loader import load_prompt
from prompt_laboratory.models import PromptDefinition
from prompt_laboratory.providers import AnthropicProvider, GeminiProvider, OpenAIProvider
from prompt_laboratory.providers.base import ProviderRequest, ProviderResponse
from prompt_laboratory.renderer import PromptRenderer


class ProviderExecutionError(RuntimeError):
    """Safe provider failure that can be shown without leaking credentials."""

    def __init__(self, provider: str, message: str, code: str = "provider_error") -> None:
        super().__init__(message)
        self.provider = provider
        self.code = code


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
            "id": "anthropic/claude-haiku-4-5-20251001",
            "label": "Anthropic · Claude Haiku 4.5",
            "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        },
        {
            "id": "gemini/gemini-3.5-flash-lite",
            "label": "Google · Gemini 3.5 Flash-Lite",
            "configured": bool(os.getenv("GEMINI_API_KEY")),
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
    elif provider_id.startswith("gemini/"):
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY is not configured")
        provider = GeminiProvider(provider_id.removeprefix("gemini/"))
    else:
        raise ValueError(f"Unsupported provider: {provider_id}")

    try:
        response = provider.generate(
            ProviderRequest(case_id="interactive-workbench", prompt=rendered)
        )
    except Exception as exc:
        error_code = getattr(exc, "code", None)
        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            code = "quota_exceeded" if error_code == "credit_balance_exhausted" else "rate_limited"
            message = (
                "This provider has no API credit remaining. Add credit and try again."
                if code == "quota_exceeded"
                else "This provider is temporarily rate limited. Try again shortly."
            )
        elif status_code in {401, 403}:
            code, message = "authentication_failed", "The provider API key is invalid or unauthorized."
        else:
            code, message = "provider_error", "The model provider could not complete this request."
        raise ProviderExecutionError(provider_id, message, code) from exc
    return rendered, response


def compare_prompt(
    prompt: PromptDefinition,
    values: dict[str, Any],
    provider_ids: list[str],
) -> tuple[str, list[dict[str, Any]]]:
    """Execute one rendered prompt concurrently across distinct providers."""
    unique_ids = list(dict.fromkeys(provider_ids))
    if len(unique_ids) < 2:
        raise ValueError("Select at least two different providers")
    rendered = PromptRenderer().render(prompt, values)
    results: list[dict[str, Any]] = []

    def run(provider_id: str) -> ProviderResponse:
        return execute_prompt(prompt, values, provider_id)[1]

    with ThreadPoolExecutor(max_workers=min(len(unique_ids), 4)) as pool:
        futures = {pool.submit(run, provider_id): provider_id for provider_id in unique_ids}
        for future in as_completed(futures):
            provider_id = futures[future]
            try:
                response = future.result()
                results.append({"provider_id": provider_id, "result": response.model_dump(), "error": None})
            except ProviderExecutionError as exc:
                results.append({
                    "provider_id": provider_id,
                    "result": None,
                    "error": {"code": exc.code, "message": str(exc)},
                })

    order = {provider_id: index for index, provider_id in enumerate(unique_ids)}
    results.sort(key=lambda item: order[item["provider_id"]])
    return rendered, results
