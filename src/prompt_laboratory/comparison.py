"""Prompt-version and model comparison reports."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from prompt_laboratory.datasets import TestDataset
from prompt_laboratory.evaluation import EvaluationReport, run_evaluation
from prompt_laboratory.models import PromptDefinition
from prompt_laboratory.pricing import PricingCatalog
from prompt_laboratory.providers.base import ModelProvider


class ComparisonRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_version: str
    provider: str
    average_score: float
    pass_rate: float
    estimated_cost_usd: float
    total_latency_ms: float
    score_delta_vs_baseline: float


class ComparisonReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    baseline: str
    rows: list[ComparisonRow]


def compare(
    prompts: list[PromptDefinition],
    dataset: TestDataset,
    providers: list[ModelProvider],
    *,
    pricing: PricingCatalog | None = None,
    baseline: tuple[str, str] | None = None,
) -> tuple[ComparisonReport, list[EvaluationReport]]:
    if not prompts or not providers:
        raise ValueError("comparison requires at least one prompt and one provider")
    reports = [
        run_evaluation(
            prompt,
            dataset,
            provider,
            pricing=pricing,
            allow_version_comparison=True,
        )
        for prompt in prompts
        for provider in providers
    ]
    baseline_key = baseline or (reports[0].prompt_version, reports[0].provider)
    baseline_report = next(
        (
            report
            for report in reports
            if (report.prompt_version, report.provider) == baseline_key
        ),
        None,
    )
    if baseline_report is None:
        raise ValueError(f"Baseline {baseline_key!r} is not present in the comparison")

    rows = [
        ComparisonRow(
            prompt_version=report.prompt_version,
            provider=report.provider,
            average_score=report.summary.average_score,
            pass_rate=report.summary.pass_rate,
            estimated_cost_usd=report.summary.estimated_cost_usd,
            total_latency_ms=report.summary.total_latency_ms,
            score_delta_vs_baseline=(
                report.summary.average_score - baseline_report.summary.average_score
            ),
        )
        for report in reports
    ]
    return (
        ComparisonReport(
            created_at=datetime.now(UTC),
            baseline=f"{baseline_key[0]} | {baseline_key[1]}",
            rows=rows,
        ),
        reports,
    )
