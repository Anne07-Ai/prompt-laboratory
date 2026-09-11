"""Provider-neutral LLM-as-judge with a strict JSON response contract."""

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from prompt_laboratory.datasets import JudgeExpectation
from prompt_laboratory.evaluators.models import EvaluationResult
from prompt_laboratory.providers.base import ModelProvider, ProviderRequest


class JudgeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class LLMJudge:
    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    def evaluate(
        self,
        case_id: str,
        rendered_prompt: str,
        response: str,
        expectation: JudgeExpectation,
    ) -> EvaluationResult:
        judge_prompt = (
            "Evaluate the candidate response using the rubric below. "
            'Return only JSON: {"score": <number from 0 to 1>, "reason": "<brief reason>"}\n\n'
            f"Rubric:\n{expectation.rubric}\n\n"
            f"Original prompt:\n{rendered_prompt}\n\nCandidate response:\n{response}"
        )
        try:
            raw = self._provider.generate(
                ProviderRequest(case_id=f"judge-{case_id}", prompt=judge_prompt)
            )
            decision = JudgeDecision.model_validate(json.loads(raw.text))
            return EvaluationResult(
                evaluator="llm_judge",
                score=decision.score,
                passed=decision.score >= expectation.minimum_score,
                details={
                    "minimum": expectation.minimum_score,
                    "reason": decision.reason,
                    "judge_provider": self._provider.name,
                },
            )
        except (KeyError, json.JSONDecodeError, ValidationError) as exc:
            return EvaluationResult(
                evaluator="llm_judge",
                score=0,
                passed=False,
                details={"error": f"Invalid judge response: {exc}"},
            )
