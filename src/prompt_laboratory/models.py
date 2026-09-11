"""Validated contracts for Git-native prompt definitions."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InputType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class OutputType(StrEnum):
    TEXT = "text"
    JSON = "json"


class VariableDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: InputType
    description: str = Field(min_length=1)
    required: bool = True
    default: Any | None = None

    @model_validator(mode="after")
    def validate_default(self) -> "VariableDefinition":
        if self.required and self.default is not None:
            raise ValueError("required variables cannot define a default")
        return self


class OutputDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: OutputType
    description: str = Field(min_length=1)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    @model_validator(mode="after")
    def validate_schema(self) -> "OutputDefinition":
        if self.type == OutputType.JSON and self.schema_ is None:
            raise ValueError("JSON outputs must define a schema")
        if self.type == OutputType.TEXT and self.schema_ is not None:
            raise ValueError("text outputs cannot define a JSON schema")
        return self


class PromptDefinition(BaseModel):
    """Stable v1 prompt contract stored in YAML."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(pattern=r"^1\.\d+$")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    task: str = Field(min_length=1)
    owners: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    template: str = Field(min_length=1)
    variables: dict[str, VariableDefinition] = Field(default_factory=dict)
    output: OutputDefinition
