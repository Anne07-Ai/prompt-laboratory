"""Offline evaluation engine and structured reporting."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from prompt_laboratory.datasets import TestDataset
from prompt_laboratory.evaluators import EvaluationResult, evaluate_response
from prompt_laboratory.models import PromptDefinition
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
    input_tokens: int
    output_tokens: int


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
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
) -> EvaluationReport:
    if dataset.prompt_id != prompt.id or dataset.prompt_version != prompt.version:
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
        evaluations = evaluate_response(response.text, test_case.expected, prompt.output)
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
            input_tokens=sum(case.response.input_tokens for case in cases),
            output_tokens=sum(case.response.output_tokens for case in cases),
        ),
        cases=cases,
    )
