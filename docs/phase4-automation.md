# Phase 4: Pull-request evaluation and regression gates

Prompt Laboratory treats prompt changes as testable software changes. The quality-gate workflow runs
when prompts, datasets, baselines, policies, evaluation code, or the workflow itself changes.

## Gate logic

Each current run must satisfy both absolute thresholds and allowed deltas from an approved baseline:

- minimum pass rate
- minimum average score
- maximum pass-rate drop
- maximum average-score drop
- optional maximum cost increase
- optional maximum latency increase

A failure records the metric, actual value, and required rule. The process exits non-zero so GitHub
can block the pull request when branch protection requires the check.

## Evidence

Every workflow run produces:

- one complete JSON evaluation report per prompt suite
- `gate-results.json` with machine-readable decisions
- `summary.md` rendered in the GitHub Actions job summary
- a downloadable artifact retained for 14 days

## Security and reproducibility

The default gate uses deterministic mock responses and requires no secrets. Real-provider checks can
be added later as a protected, explicitly authorized workflow. Baselines are reviewed Git artifacts;
the gate never updates them automatically, preventing a regressive change from approving itself.
