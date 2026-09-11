"""Adapter for local OpenAI-compatible HTTP endpoints."""

import json
from time import perf_counter
from urllib.request import Request, urlopen

from prompt_laboratory.providers.base import ProviderRequest, ProviderResponse


class LocalProvider:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._timeout = timeout

    @property
    def name(self) -> str:
        return f"local/{self._model}"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        payload = json.dumps(
            {
                "model": self._model,
                "messages": [{"role": "user", "content": request.prompt}],
                "temperature": 0,
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        started = perf_counter()
        with urlopen(
            Request(self._url, data=payload, headers=headers, method="POST"),
            timeout=self._timeout,
        ) as remote:
            body = json.loads(remote.read())
        usage = body.get("usage", {})
        text = body["choices"][0]["message"]["content"]
        return ProviderResponse(
            text=text,
            provider="local",
            model=self._model,
            latency_ms=(perf_counter() - started) * 1000,
            input_tokens=usage.get("prompt_tokens", len(request.prompt.split())),
            output_tokens=usage.get("completion_tokens", len(text.split())),
        )
