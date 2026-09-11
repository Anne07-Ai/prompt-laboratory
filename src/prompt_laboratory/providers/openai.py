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
        return ProviderResponse(
            text=response.output_text,
            provider="openai",
            model=self._model,
            latency_ms=(perf_counter() - started) * 1000,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
