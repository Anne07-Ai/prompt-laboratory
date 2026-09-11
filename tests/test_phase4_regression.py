from datetime import UTC, datetime
from pathlib import Path

from prompt_laboratory.evaluation import EvaluationReport, RunSummary
from prompt_laboratory.regression import (
    BaselineMetrics,
    RegressionPolicy,
    evaluate_regression,
)
from prompt_laboratory.repository_gate import run_repository_gate


ROOT = Path(__file__).parents[1]


def make_report(score: float, pass_rate: float) -> EvaluationReport:
    return EvaluationReport(
        created_at=datetime.now(UTC),
        prompt_id="example.prompt",
        prompt_version="1.1.0",
        provider="mock/local-deterministic",
        summary=RunSummary(
            total_cases=1,
            passed_cases=int(pass_rate == 1),
            failed_cases=int(pass_rate != 1),
            pass_rate=pass_rate,
            average_score=score,
            total_latency_ms=10,
            input_tokens=10,
            output_tokens=10,
            estimated_cost_usd=0.01,
        ),
        cases=[],
    )


BASELINE = BaselineMetrics(
    prompt_version="1.0.0",
    provider="mock/local-deterministic",
    pass_rate=1,
    average_score=0.95,
    estimated_cost_usd=0.01,
    total_latency_ms=10,
)


def test_gate_passes_score_within_policy() -> None:
    result = evaluate_regression(
        make_report(0.94, 1),
        BASELINE,
        RegressionPolicy(minimum_average_score=0.9, maximum_average_score_drop=0.02),
    )
    assert result.passed is True


def test_gate_reports_absolute_and_baseline_regressions() -> None:
    result = evaluate_regression(
        make_report(0.80, 0),
        BASELINE,
        RegressionPolicy(minimum_average_score=0.9),
    )
    assert result.passed is False
    assert {violation.metric for violation in result.violations} == {
        "pass_rate",
        "average_score",
        "pass_rate_drop",
        "average_score_drop",
    }


def test_cost_and_latency_limits_are_optional() -> None:
    report = make_report(0.95, 1)
    report.summary.estimated_cost_usd = 0.02
    report.summary.total_latency_ms = 20
    result = evaluate_regression(
        report,
        BASELINE,
        RegressionPolicy(
            maximum_cost_increase_ratio=0.5,
            maximum_latency_increase_ratio=0.5,
        ),
    )
    assert {violation.metric for violation in result.violations} == {
        "cost_increase_ratio",
        "latency_increase_ratio",
    }


def test_repository_gate_evaluates_every_industry(tmp_path: Path) -> None:
    result = run_repository_gate(
        ROOT,
        tmp_path,
        ROOT / "configs/regression-policy.yaml",
        ROOT / "baselines/mock-baseline.json",
    )
    assert result.passed is True
    assert len(result.evaluations) == 6
    assert (tmp_path / "gate-results.json").exists()
    assert "Overall: **PASS**" in (tmp_path / "summary.md").read_text(encoding="utf-8")
