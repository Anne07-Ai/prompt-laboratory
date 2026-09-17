"""Google Gemini generate-content adapter."""

from time import perf_counter
from typing import Any

from prompt_laboratory.providers.base import ProviderRequest, ProviderResponse


class GeminiProvider:
    def __init__(
        self, model: str, *, client: Any | None = None, api_key: str | None = None
    ) -> None:
        if client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError(
                    'Install Gemini support with: pip install "prompt-laboratory[gemini]"'
                ) from exc
            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model

    @property
    def name(self) -> str:
        return f"gemini/{self._model}"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        started = perf_counter()
        response = self._client.models.generate_content(
            model=self._model,
            contents=request.prompt,
        )
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count or 0
        output_tokens = usage.candidates_token_count or 0
        estimated_cost = 0.0
        if self._model.startswith("gemini-3.5-flash-lite"):
            estimated_cost = (input_tokens * 0.30 + output_tokens * 2.50) / 1_000_000
        return ProviderResponse(
            text=response.text or "",
            provider="gemini",
            model=self._model,
            latency_ms=(perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
        )
