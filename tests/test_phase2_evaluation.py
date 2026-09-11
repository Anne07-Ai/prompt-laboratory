import json
from pathlib import Path

import pytest

from prompt_laboratory.datasets import DatasetLoadError, load_dataset
from prompt_laboratory.evaluation import run_evaluation
from prompt_laboratory.loader import load_prompt
from prompt_laboratory.providers.mock import MockProvider

ROOT = Path(__file__).parents[1]
DATASETS = sorted((ROOT / "datasets").glob("*/*.yaml"))


@pytest.mark.parametrize("dataset_path", DATASETS, ids=lambda path: path.parent.name)
def test_every_industry_fixture_passes_offline(dataset_path: Path) -> None:
    dataset = load_dataset(dataset_path)
    prompt_path = next(
        path for path in (ROOT / "prompts").glob("*/*.yaml") if load_prompt(path).id == dataset.prompt_id
    )
    prompt = load_prompt(prompt_path)
    provider = MockProvider({case.id: case.mock_response for case in dataset.cases})

    report = run_evaluation(prompt, dataset, provider)

    assert report.summary.total_cases >= 1
    assert report.summary.pass_rate == 1.0
    assert report.summary.input_tokens > 0


def test_json_schema_failure_is_auditable() -> None:
    prompt = load_prompt(ROOT / "prompts/hr/cv-extraction.yaml")
    dataset = load_dataset(ROOT / "datasets/hr/cv-extraction.yaml")
    report = run_evaluation(prompt, dataset, MockProvider({"structured-cv": '{"skills": 42}'}))

    assert report.summary.failed_cases == 1
    schema_result = next(
        result for result in report.cases[0].evaluations if result.evaluator == "json_schema"
    )
    assert schema_result.passed is False
    assert "error" in schema_result.details


def test_prompt_version_mismatch_fails_before_execution() -> None:
    prompt = load_prompt(ROOT / "prompts/education/concept-explanation.yaml")
    dataset = load_dataset(ROOT / "datasets/education/concept-explanation.yaml")
    dataset.prompt_version = "9.9.9"

    with pytest.raises(ValueError, match="Dataset targets"):
        run_evaluation(prompt, dataset, MockProvider({}))


def test_report_writes_structured_json(tmp_path: Path) -> None:
    prompt = load_prompt(ROOT / "prompts/education/concept-explanation.yaml")
    dataset = load_dataset(ROOT / "datasets/education/concept-explanation.yaml")
    provider = MockProvider({case.id: case.mock_response for case in dataset.cases})
    path = run_evaluation(prompt, dataset, provider).write_json(tmp_path / "report.json")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["prompt_id"] == prompt.id
    assert payload["summary"]["pass_rate"] == 1.0


def test_duplicate_case_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text(
        """
schema_version: "1.0"
prompt_id: example.prompt
prompt_version: "1.0.0"
cases:
  - &case
    id: repeated
    inputs: {}
    mock_response: ok
    expected: {exact_match: ok}
  - *case
""",
        encoding="utf-8",
    )
    with pytest.raises(DatasetLoadError, match="unique"):
        load_dataset(path)
