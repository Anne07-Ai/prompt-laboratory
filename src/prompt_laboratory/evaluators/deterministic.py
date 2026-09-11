"""Exact-match, keyword, JSON-Schema, and similarity evaluators."""

import json
import re
from typing import Any

from jsonschema import ValidationError, validate

from prompt_laboratory.datasets import ExpectedOutput
from prompt_laboratory.evaluators.models import EvaluationResult
from prompt_laboratory.evaluators.similarity import token_similarity
from prompt_laboratory.models import OutputDefinition, OutputType


def _normalize(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def evaluate_response(
    response: str,
    expected: ExpectedOutput,
    output: OutputDefinition,
) -> list[EvaluationResult]:
    results: list[EvaluationResult] = []

    if expected.exact_match is not None:
        actual = response.strip() if expected.case_sensitive else _normalize(response)
        target = (
            expected.exact_match.strip()
            if expected.case_sensitive
            else _normalize(expected.exact_match)
        )
        passed = actual == target
        results.append(
            EvaluationResult(
                evaluator="exact_match",
                score=float(passed),
                passed=passed,
                details={"case_sensitive": expected.case_sensitive},
            )
        )

    if expected.keywords:
        haystack = response if expected.case_sensitive else response.casefold()
        matched: list[str] = []
        for keyword in expected.keywords:
            needle = keyword if expected.case_sensitive else keyword.casefold()
            if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack):
                matched.append(keyword)
        score = len(matched) / len(expected.keywords)
        results.append(
            EvaluationResult(
                evaluator="keywords",
                score=score,
                passed=score == 1.0,
                details={
                    "matched": matched,
                    "missing": [item for item in expected.keywords if item not in matched],
                },
            )
        )

    if expected.similarity_reference is not None:
        results.append(
            token_similarity(
                response,
                expected.similarity_reference,
                expected.minimum_similarity,
            )
        )

    if output.type == OutputType.JSON:
        details: dict[str, Any] = {}
        try:
            value = json.loads(response)
            validate(instance=value, schema=output.schema_)
            passed = True
        except (json.JSONDecodeError, ValidationError) as exc:
            passed = False
            details["error"] = str(exc)
        results.append(
            EvaluationResult(
                evaluator="json_schema",
                score=float(passed),
                passed=passed,
                details=details,
            )
        )

    return results
