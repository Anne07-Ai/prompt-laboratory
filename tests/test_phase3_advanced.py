from pathlib import Path
from types import SimpleNamespace

import pytest

from prompt_laboratory.comparison import compare
from prompt_laboratory.datasets import ExpectedOutput, JudgeExpectation, load_dataset
from prompt_laboratory.evaluators.judge import LLMJudge
from prompt_laboratory.evaluators.similarity import token_similarity
from prompt_laboratory.loader import load_prompt
from prompt_laboratory.pricing import PricingCatalog
from prompt_laboratory.providers.anthropic import AnthropicProvider
from prompt_laboratory.providers.base import ProviderRequest
from prompt_laboratory.providers.mock import MockProvider
from prompt_laboratory.providers.openai import OpenAIProvider

ROOT = Path(__file__).parents[1]


class FakeOpenAI:
    def __init__(self) -> None:
        self.responses = self

    def create(self, **kwargs):
        assert kwargs["input"] == "hello"
        return SimpleNamespace(
            output_text="world",
            usage=SimpleNamespace(input_tokens=2, output_tokens=1),
        )


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = self

    def create(self, **kwargs):
        assert kwargs["messages"][0]["content"] == "hello"
        return SimpleNamespace(
            content=[SimpleNamespace(text="world")],
            usage=SimpleNamespace(input_tokens=2, output_tokens=1),
        )


def test_openai_adapter_normalizes_response() -> None:
    result = OpenAIProvider("test-model", client=FakeOpenAI()).generate(
        ProviderRequest(case_id="one", prompt="hello")
    )
    assert result.provider == "openai"
    assert result.text == "world"
    assert result.input_tokens == 2


def test_anthropic_adapter_normalizes_response() -> None:
    result = AnthropicProvider("test-model", client=FakeAnthropic()).generate(
        ProviderRequest(case_id="one", prompt="hello")
    )
    assert result.provider == "anthropic"
    assert result.text == "world"
    assert result.output_tokens == 1


def test_similarity_has_threshold_and_evidence() -> None:
    result = token_similarity("plants need bright sunlight", "plants use sunlight", 0.4)
    assert result.score == pytest.approx(0.4)
    assert result.passed is True
    assert result.details["metric"] == "token-set-jaccard"


def test_pricing_uses_separate_input_and_output_rates() -> None:
    catalog = PricingCatalog.model_validate(
        {
            "models": {
                "mock/local-deterministic": {
                    "input_per_million_usd": 1,
                    "output_per_million_usd": 3,
                }
            }
        }
    )
    assert catalog.estimate("mock/local-deterministic", 1000, 2000) == pytest.approx(0.007)


def test_llm_judge_accepts_valid_structured_decision() -> None:
    judge = LLMJudge(
        MockProvider({"judge-case": '{"score":0.8,"reason":"Grounded and complete"}'})
    )
    result = judge.evaluate(
        "case",
        "Explain gravity",
        "Gravity attracts masses.",
        JudgeExpectation(rubric="Accurate and concise", minimum_score=0.7),
    )
    assert result.passed is True
    assert result.score == 0.8


def test_llm_judge_rejects_malformed_decision() -> None:
    judge = LLMJudge(MockProvider({"judge-case": "not json"}))
    result = judge.evaluate(
        "case",
        "Explain gravity",
        "Gravity attracts masses.",
        JudgeExpectation(rubric="Accurate"),
    )
    assert result.passed is False
    assert "error" in result.details


def test_model_comparison_reports_delta_from_baseline() -> None:
    prompt = load_prompt(ROOT / "prompts/education/concept-explanation.yaml")
    dataset = load_dataset(ROOT / "datasets/education/concept-explanation.yaml")
    good = MockProvider({dataset.cases[0].id: dataset.cases[0].mock_response or ""})
    poor = MockProvider({dataset.cases[0].id: "unrelated output"})
    good._responses = dict(good._responses)
    poor._responses = dict(poor._responses)

    comparison, reports = compare([prompt], dataset, [good, poor])

    assert len(reports) == 2
    assert comparison.rows[0].score_delta_vs_baseline == 0
    assert comparison.rows[1].score_delta_vs_baseline < 0


def test_expected_output_accepts_similarity_only() -> None:
    expected = ExpectedOutput(similarity_reference="reference", minimum_similarity=0.5)
    assert expected.similarity_reference == "reference"
