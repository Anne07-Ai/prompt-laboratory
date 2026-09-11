"""Normalized evaluator result."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator: str
    score: float = Field(ge=0, le=1)
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)
