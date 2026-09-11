"""Validated evaluation-dataset contracts."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DatasetLoadError(ValueError):
    """Raised when an evaluation dataset cannot be loaded."""


class JudgeExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric: str = Field(min_length=1)
    minimum_score: float = Field(default=0.7, ge=0, le=1)


class ExpectedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exact_match: str | None = None
    keywords: list[str] = Field(default_factory=list)
    case_sensitive: bool = False
    similarity_reference: str | None = None
    minimum_similarity: float = Field(default=0.7, ge=0, le=1)
    judge: JudgeExpectation | None = None

    @model_validator(mode="after")
    def require_expectation(self) -> "ExpectedOutput":
        if (
            self.exact_match is None
            and not self.keywords
            and self.similarity_reference is None
            and self.judge is None
        ):
            raise ValueError("at least one evaluation expectation is required")
        return self


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    inputs: dict[str, Any]
    mock_response: str | None = None
    expected: ExpectedOutput


class TestDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    prompt_id: str
    prompt_version: str = Field(pattern=r"^(\d+\.\d+\.\d+|\*)$")
    cases: list[TestCase] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_ids(self) -> "TestDataset":
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("dataset case IDs must be unique")
        return self


def load_dataset(path: str | Path) -> TestDataset:
    dataset_path = Path(path)
    try:
        raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
        return TestDataset.model_validate(raw)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise DatasetLoadError(f"Invalid dataset {dataset_path}: {exc}") from exc
