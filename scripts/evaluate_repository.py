"""Run repository-wide prompt regression checks."""

import argparse
from pathlib import Path

from prompt_laboratory.repository_gate import run_repository_gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("reports/ci"))
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("configs/regression-policy.yaml"),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("baselines/mock-baseline.json"),
    )
    args = parser.parse_args()
    result = run_repository_gate(
        args.root,
        args.output,
        args.policy,
        args.baseline,
    )
    print(f"Evaluated {len(result.evaluations)} prompt suites")
    for gate in result.gates:
        print(f"{gate.prompt_id}: {'PASS' if gate.passed else 'FAIL'}")
        for violation in gate.violations:
            print(
                f"  {violation.metric}: {violation.actual:.6f} "
                f"(required {violation.required})"
            )
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
