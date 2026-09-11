"""Dependency-free token-set similarity evaluator."""

import re

from prompt_laboratory.evaluators.models import EvaluationResult


def token_similarity(response: str, reference: str, minimum: float) -> EvaluationResult:
    def tokens(value: str) -> set[str]:
        return set(re.findall(r"\w+", value.casefold()))

    actual = tokens(response)
    expected = tokens(reference)
    union = actual | expected
    score = len(actual & expected) / len(union) if union else 1.0
    return EvaluationResult(
        evaluator="token_similarity",
        score=score,
        passed=score >= minimum,
        details={"minimum": minimum, "metric": "token-set-jaccard"},
    )
