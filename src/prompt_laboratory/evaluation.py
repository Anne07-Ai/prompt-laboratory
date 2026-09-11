"""Evaluation engine with usage, latency, and cost reporting."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from prompt_laboratory.datasets import TestDataset
from prompt_laboratory.evaluators import EvaluationResult, LLMJudge, evaluate_response
from prompt_laboratory.models import PromptDefinition
from prompt_laboratory.pricing import PricingCatalog
from prompt_laboratory.providers.base import ModelProvider, ProviderRequest, ProviderResponse
from prompt_laboratory.renderer import PromptRenderer


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    rendered_prompt: str
    response: ProviderResponse
    evaluations: list[EvaluationResult]
    passed: bool
    score: float = Field(ge=0, le=1)


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float = Field(ge=0, le=1)
    average_score: float = Field(ge=0, le=1)
    total_latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.1"
    created_at: datetime
    prompt_id: str
    prompt_version: str
    provider: str
    summary: RunSummary
    cases: list[CaseResult]

    def write_json(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return output_path


def run_evaluation(
    prompt: PromptDefinition,
    dataset: TestDataset,
    provider: ModelProvider,
    *,
    pricing: PricingCatalog | None = None,
    judge: LLMJudge | None = None,
    allow_version_comparison: bool = False,
) -> EvaluationReport:
    version_matches = dataset.prompt_version in {"*", prompt.version}
    if dataset.prompt_id != prompt.id or (not version_matches and not allow_version_comparison):
        raise ValueError(
            "Dataset targets "
            f"{dataset.prompt_id}@{dataset.prompt_version}, "
            f"but prompt is {prompt.id}@{prompt.version}"
        )

    renderer = PromptRenderer()
    cases: list[CaseResult] = []
    for test_case in dataset.cases:
        rendered = renderer.render(prompt, test_case.inputs)
        response = provider.generate(ProviderRequest(case_id=test_case.id, prompt=rendered))
        if pricing is not None:
            response.estimated_cost_usd = pricing.estimate(
                provider.name,
                response.input_tokens,
                response.output_tokens,
            )
        evaluations = evaluate_response(response.text, test_case.expected, prompt.output)
        if test_case.expected.judge is not None:
            if judge is None:
                raise ValueError(f"Case {test_case.id!r} requires an LLM judge")
            evaluations.append(
                judge.evaluate(
                    test_case.id,
                    rendered,
                    response.text,
                    test_case.expected.judge,
                )
            )
        if not evaluations:
            raise ValueError(f"Case {test_case.id!r} has no applicable evaluators")
        score = sum(result.score for result in evaluations) / len(evaluations)
        cases.append(
            CaseResult(
                case_id=test_case.id,
                rendered_prompt=rendered,
                response=response,
                evaluations=evaluations,
                passed=all(result.passed for result in evaluations),
                score=score,
            )
        )

    passed = sum(case.passed for case in cases)
    return EvaluationReport(
        created_at=datetime.now(UTC),
        prompt_id=prompt.id,
        prompt_version=prompt.version,
        provider=provider.name,
        summary=RunSummary(
            total_cases=len(cases),
            passed_cases=passed,
            failed_cases=len(cases) - passed,
            pass_rate=passed / len(cases),
            average_score=sum(case.score for case in cases) / len(cases),
            total_latency_ms=sum(case.response.latency_ms for case in cases),
            input_tokens=sum(case.response.input_tokens for case in cases),
            output_tokens=sum(case.response.output_tokens for case in cases),
            estimated_cost_usd=sum(case.response.estimated_cost_usd for case in cases),
        ),
        cases=cases,
    )
