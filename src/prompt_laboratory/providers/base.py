"""Provider-neutral execution contracts."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class ProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    prompt: str


class ProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    provider: str
    model: str
    latency_ms: float = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)


class ModelProvider(Protocol):
    @property
    def name(self) -> str: ...

    def generate(self, request: ProviderRequest) -> ProviderResponse: ...
