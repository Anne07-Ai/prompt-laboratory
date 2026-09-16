"""Anthropic Messages API adapter."""

from time import perf_counter
from typing import Any

from prompt_laboratory.providers.base import ProviderRequest, ProviderResponse


class AnthropicProvider:
    def __init__(
        self,
        model: str,
        *,
        client: Any | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> None:
        if client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise RuntimeError(
                    'Install Anthropic support with: pip install "prompt-laboratory[anthropic]"'
                ) from exc
            client = Anthropic()
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    @property
    def name(self) -> str:
        return f"anthropic/{self._model}"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        started = perf_counter()
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            messages=[{"role": "user", "content": request.prompt}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        estimated_cost = 0.0
        if self._model.startswith("claude-haiku-4-5"):
            estimated_cost = (input_tokens * 1.00 + output_tokens * 5.00) / 1_000_000
        return ProviderResponse(
            text=text,
            provider="anthropic",
            model=self._model,
            latency_ms=(perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
        )
