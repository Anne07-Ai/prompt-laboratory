"""Repository-wide offline evaluation and regression gate."""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from prompt_laboratory.datasets import load_dataset
from prompt_laboratory.evaluation import EvaluationReport, run_evaluation
from prompt_laboratory.loader import load_prompt
from prompt_laboratory.providers.mock import MockProvider
from prompt_laboratory.regression import (
    BaselineSnapshot,
    GateResult,
    RegressionPolicy,
    evaluate_regression,
    write_gate_results,
)


class RepositoryGateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    evaluations: list[EvaluationReport]
    gates: list[GateResult]


def run_repository_gate(
    root: str | Path,
    output_dir: str | Path,
    policy_path: str | Path,
    baseline_path: str | Path,
) -> RepositoryGateReport:
    root_path = Path(root)
    output_path = Path(output_dir)
    prompts = {
        prompt.id: prompt
        for prompt in (
            load_prompt(path) for path in sorted((root_path / "prompts").glob("*/*.yaml"))
        )
    }
    policy = RegressionPolicy.from_yaml(policy_path)
    baselines = BaselineSnapshot.from_json(baseline_path)
    reports: list[EvaluationReport] = []
    gates: list[GateResult] = []

    for dataset_path in sorted((root_path / "datasets").glob("*/*.yaml")):
        dataset = load_dataset(dataset_path)
        if dataset.prompt_id not in prompts:
            raise ValueError(f"No prompt found for dataset {dataset_path}: {dataset.prompt_id}")
        if any(case.mock_response is None for case in dataset.cases):
            raise ValueError(f"CI dataset {dataset_path} requires mock_response for every case")
        prompt = prompts[dataset.prompt_id]
        provider = MockProvider(
            {case.id: case.mock_response or "" for case in dataset.cases}
        )
        report = run_evaluation(prompt, dataset, provider)
        if report.prompt_id not in baselines.runs:
            raise ValueError(f"No approved baseline for {report.prompt_id}")
        gate = evaluate_regression(report, baselines.runs[report.prompt_id], policy)
        report.write_json(output_path / f"{report.prompt_id}.json")
        reports.append(report)
        gates.append(gate)

    write_gate_results(gates, output_path / "gate-results.json")
    markdown = _markdown_summary(reports, gates)
    (output_path / "summary.md").write_text(markdown, encoding="utf-8")
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(markdown)

    return RepositoryGateReport(
        passed=all(gate.passed for gate in gates),
        evaluations=reports,
        gates=gates,
    )


def _markdown_summary(
    reports: list[EvaluationReport],
    gates: list[GateResult],
) -> str:
    gate_by_id = {gate.prompt_id: gate for gate in gates}
    lines = [
        "## Prompt Laboratory quality gate",
        "",
        "| Prompt | Version | Score | Pass rate | Gate |",
        "|---|---:|---:|---:|---|",
    ]
    for report in reports:
        gate = gate_by_id[report.prompt_id]
        status = "PASS" if gate.passed else "FAIL"
        lines.append(
            f"| {report.prompt_id} | {report.prompt_version} | "
            f"{report.summary.average_score:.3f} | {report.summary.pass_rate:.1%} | {status} |"
        )
    lines.extend(["", f"Overall: **{'PASS' if all(g.passed for g in gates) else 'FAIL'}**", ""])
    return "\n".join(lines)
