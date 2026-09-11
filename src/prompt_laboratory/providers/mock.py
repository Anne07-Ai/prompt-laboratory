"""Deterministic offline provider used by local development and CI."""

from prompt_laboratory.providers.base import ProviderRequest, ProviderResponse


class MockProvider:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses

    @property
    def name(self) -> str:
        return "mock/local-deterministic"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if request.case_id not in self._responses:
            raise KeyError(f"No mock response configured for case {request.case_id!r}")
        text = self._responses[request.case_id]
        return ProviderResponse(
            text=text,
            provider="mock",
            model="local-deterministic",
            latency_ms=0.0,
            input_tokens=len(request.prompt.split()),
            output_tokens=len(text.split()),
        )
