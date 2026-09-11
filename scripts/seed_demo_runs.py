"""Seed a local Prompt Laboratory API with a realistic version-comparison story."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import httpx


def demo_reports() -> list[dict[str, object]]:
    now = datetime.now(UTC)
    observations = [
        ("0.8.0", 0.72, 0.67, 1510, 0.0024),
        ("0.9.0", 0.81, 0.80, 1380, 0.0021),
        ("1.0.0", 0.91, 1.00, 1190, 0.0018),
    ]
    reports = []
    for index, (version, score, pass_rate, latency, cost) in enumerate(observations):
        passed = round(pass_rate * 5)
        reports.append(
            {
                "schema_version": "1.1",
                "created_at": (now - timedelta(days=2 - index)).isoformat(),
                "prompt_id": "healthcare.patient-explanation",
                "prompt_version": version,
                "provider": "openai/gpt-4.1-mini",
                "summary": {
                    "total_cases": 5,
                    "passed_cases": passed,
                    "failed_cases": 5 - passed,
                    "pass_rate": pass_rate,
                    "average_score": score,
                    "total_latency_ms": latency,
                    "input_tokens": 420,
                    "output_tokens": 180,
                    "estimated_cost_usd": cost,
                },
                "cases": [],
            }
        )
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    args = parser.parse_args()
    with httpx.Client(base_url=args.api_url, timeout=10) as client:
        for report in demo_reports():
            response = client.post("/api/v1/runs", json=report)
            response.raise_for_status()
            print(f"Created {report['prompt_version']}: {response.json()['id']}")


if __name__ == "__main__":
    main()
