"""Configurable, evidence-rich quality regression gates."""

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from prompt_laboratory.evaluation import EvaluationReport


class RegressionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    minimum_pass_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_average_score: float = Field(default=0.9, ge=0, le=1)
    maximum_pass_rate_drop: float = Field(default=0.0, ge=0, le=1)
    maximum_average_score_drop: float = Field(default=0.02, ge=0, le=1)
    maximum_cost_increase_ratio: float | None = Field(default=None, ge=0)
    maximum_latency_increase_ratio: float | None = Field(default=None, ge=0)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RegressionPolicy":
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class BaselineMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_version: str
    provider: str
    pass_rate: float = Field(ge=0, le=1)
    average_score: float = Field(ge=0, le=1)
    estimated_cost_usd: float = Field(ge=0)
    total_latency_ms: float = Field(ge=0)


class BaselineSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    runs: dict[str, BaselineMetrics]

    @classmethod
    def from_json(cls, path: str | Path) -> "BaselineSnapshot":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class GateViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    actual: float
    required: str


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    passed: bool
    violations: list[GateViolation]


def evaluate_regression(
    report: EvaluationReport,
    baseline: BaselineMetrics,
    policy: RegressionPolicy,
) -> GateResult:
    current = report.summary
    violations: list[GateViolation] = []

    def require(metric: str, actual: float, passed: bool, rule: str) -> None:
        if not passed:
            violations.append(GateViolation(metric=metric, actual=actual, required=rule))

    require(
        "pass_rate",
        current.pass_rate,
        current.pass_rate >= policy.minimum_pass_rate,
        f">= {policy.minimum_pass_rate}",
    )
    require(
        "average_score",
        current.average_score,
        current.average_score >= policy.minimum_average_score,
        f">= {policy.minimum_average_score}",
    )
    pass_drop = baseline.pass_rate - current.pass_rate
    score_drop = baseline.average_score - current.average_score
    require(
        "pass_rate_drop",
        pass_drop,
        pass_drop <= policy.maximum_pass_rate_drop,
        f"<= {policy.maximum_pass_rate_drop}",
    )
    require(
        "average_score_drop",
        score_drop,
        score_drop <= policy.maximum_average_score_drop,
        f"<= {policy.maximum_average_score_drop}",
    )

    if policy.maximum_cost_increase_ratio is not None and baseline.estimated_cost_usd > 0:
        ratio = current.estimated_cost_usd / baseline.estimated_cost_usd - 1
        require(
            "cost_increase_ratio",
            ratio,
            ratio <= policy.maximum_cost_increase_ratio,
            f"<= {policy.maximum_cost_increase_ratio}",
        )
    if policy.maximum_latency_increase_ratio is not None and baseline.total_latency_ms > 0:
        ratio = current.total_latency_ms / baseline.total_latency_ms - 1
        require(
            "latency_increase_ratio",
            ratio,
            ratio <= policy.maximum_latency_increase_ratio,
            f"<= {policy.maximum_latency_increase_ratio}",
        )

    return GateResult(
        prompt_id=report.prompt_id,
        passed=not violations,
        violations=violations,
    )


def write_gate_results(results: list[GateResult], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "passed": all(result.passed for result in results),
                "results": [result.model_dump() for result in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return target
