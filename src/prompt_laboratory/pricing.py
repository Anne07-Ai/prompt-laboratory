"""Version-controlled model pricing and cost estimation."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ModelPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_per_million_usd: float = Field(ge=0)
    output_per_million_usd: float = Field(ge=0)


class PricingCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    models: dict[str, ModelPrice]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PricingCatalog":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(raw)

    def estimate(self, provider_model: str, input_tokens: int, output_tokens: int) -> float:
        if provider_model not in self.models:
            raise KeyError(f"No pricing configured for {provider_model!r}")
        price = self.models[provider_model]
        return (
            input_tokens * price.input_per_million_usd
            + output_tokens * price.output_per_million_usd
        ) / 1_000_000
