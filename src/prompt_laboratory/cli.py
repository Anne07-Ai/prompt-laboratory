"""Command-line interface for reproducible local evaluations."""

import argparse
from pathlib import Path

from prompt_laboratory.datasets import load_dataset
from prompt_laboratory.evaluation import run_evaluation
from prompt_laboratory.loader import load_prompt
from prompt_laboratory.providers.mock import MockProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prompt-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate", help="Run an offline deterministic evaluation")
    evaluate.add_argument("--prompt", type=Path, required=True)
    evaluate.add_argument("--dataset", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    prompt = load_prompt(args.prompt)
    dataset = load_dataset(args.dataset)
    provider = MockProvider({case.id: case.mock_response for case in dataset.cases})
    report = run_evaluation(prompt, dataset, provider)
    output = report.write_json(args.output)
    summary = report.summary

    print(f"Prompt: {report.prompt_id}@{report.prompt_version}")
    print(f"Provider: {report.provider}")
    print(
        f"Cases: {summary.total_cases} | Passed: {summary.passed_cases} | "
        f"Pass rate: {summary.pass_rate:.1%} | Average score: {summary.average_score:.3f}"
    )
    print(f"Report: {output}")
    return 0 if summary.failed_cases == 0 else 1
