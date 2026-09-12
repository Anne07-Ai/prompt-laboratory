"""OpenAI Responses API adapter."""

from time import perf_counter
from typing import Any

from prompt_laboratory.providers.base import ProviderRequest, ProviderResponse


class OpenAIProvider:
    def __init__(
        self,
        model: str,
        *,
        client: Any | None = None,
        temperature: float = 0.0,
    ) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    'Install OpenAI support with: pip install "prompt-laboratory[openai]"'
                ) from exc
            client = OpenAI()
        self._client = client
        self._model = model
        self._temperature = temperature

    @property
    def name(self) -> str:
        return f"openai/{self._model}"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        started = perf_counter()
        response = self._client.responses.create(
            model=self._model,
            input=request.prompt,
            temperature=self._temperature,
        )
        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        # GPT-4.1 mini standard text rates verified against OpenAI's model page.
        estimated_cost = 0.0
        if self._model.startswith("gpt-4.1-mini"):
            estimated_cost = (input_tokens * 0.40 + output_tokens * 1.60) / 1_000_000
        return ProviderResponse(
            text=response.output_text,
            provider="openai",
            model=self._model,
            latency_ms=(perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
        )
