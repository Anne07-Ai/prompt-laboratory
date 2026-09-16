from types import SimpleNamespace

import pytest

from prompt_laboratory.providers.base import ProviderRequest
from prompt_laboratory.providers.gemini import GeminiProvider
from prompt_laboratory.workbench import provider_options


class FakeGeminiModels:
    def generate_content(self, **kwargs):
        assert kwargs == {"model": "gemini-3.5-flash-lite", "contents": "hello"}
        return SimpleNamespace(
            text="world",
            usage_metadata=SimpleNamespace(
                prompt_token_count=2,
                candidates_token_count=1,
            ),
        )


class FakeGemini:
    def __init__(self) -> None:
        self.models = FakeGeminiModels()


def test_gemini_adapter_normalizes_usage_and_cost() -> None:
    result = GeminiProvider(
        "gemini-3.5-flash-lite",
        client=FakeGemini(),
    ).generate(ProviderRequest(case_id="one", prompt="hello"))

    assert result.provider == "gemini"
    assert result.model == "gemini-3.5-flash-lite"
    assert result.text == "world"
    assert result.input_tokens == 2
    assert result.output_tokens == 1
    assert result.estimated_cost_usd == pytest.approx((2 * 0.30 + 1 * 2.50) / 1_000_000)


def test_provider_options_report_all_configured_keys(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_KEY", "test")

    options = {item["id"]: item for item in provider_options()}

    assert options["openai/gpt-4.1-mini"]["configured"] is True
    assert options["anthropic/claude-haiku-4-5-20251001"]["configured"] is True
    assert options["gemini/gemini-3.5-flash-lite"]["configured"] is True
