# Phase 3: Advanced evaluation

Phase 3 adds vendor-neutral real-model execution, token-set similarity, structured LLM-as-judge,
version-controlled pricing, and comparable experiment reports.

## Provider boundary

All providers accept a `ProviderRequest` and return a `ProviderResponse`. Vendor SDK objects never
cross this boundary. OpenAI uses the Responses API, Anthropic uses the Messages API, and local models
use an OpenAI-compatible HTTP endpoint.

SDK imports are optional and lazy. Installing the base package and running CI does not require vendor
credentials:

```bash
pip install -e ".[openai]"
pip install -e ".[anthropic]"
# or
pip install -e ".[providers]"
```

## Evaluation policy

Deterministic checks remain primary. Token similarity uses a transparent token-set Jaccard score.
LLM-as-judge requires a strict JSON decision and records the judge model in its evidence. A malformed
judge response fails closed.

## Pricing policy

Pricing is externalized to YAML because vendor rates change. The included file contains illustrative
values only; users must verify current pricing before reporting real costs.

## Comparison policy

The comparison engine runs the Cartesian product of selected prompt versions and providers against
one dataset. It records score, pass rate, cost, latency, and score delta from an explicit baseline.
Version mismatch bypass is private to this controlled comparison path; ordinary single runs remain
strict.
