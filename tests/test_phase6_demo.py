from prompt_laboratory.evaluation import EvaluationReport
from scripts.seed_demo_runs import demo_reports


def test_demo_story_contains_valid_improving_reports() -> None:
    reports = [EvaluationReport.model_validate(report) for report in demo_reports()]
    assert [report.prompt_version for report in reports] == ["0.8.0", "0.9.0", "1.0.0"]
    assert [report.summary.average_score for report in reports] == sorted(
        report.summary.average_score for report in reports
    )
    assert reports[-1].summary.pass_rate == 1
