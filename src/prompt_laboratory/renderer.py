"""Strict, typed rendering for prompt templates."""

from typing import Any

from jinja2 import Environment, StrictUndefined, meta
from jinja2.exceptions import TemplateError

from prompt_laboratory.models import InputType, PromptDefinition


class PromptRenderError(ValueError):
    """Raised when a prompt contract or runtime input is invalid."""


_TYPE_LABELS = {
    InputType.STRING: "a string",
    InputType.INTEGER: "an integer",
    InputType.NUMBER: "a number",
    InputType.BOOLEAN: "a boolean",
    InputType.OBJECT: "an object",
    InputType.ARRAY: "an array",
}

_PYTHON_TYPES: dict[InputType, type | tuple[type, ...]] = {
    InputType.STRING: str,
    InputType.INTEGER: int,
    InputType.NUMBER: (int, float),
    InputType.BOOLEAN: bool,
    InputType.OBJECT: dict,
    InputType.ARRAY: list,
}


class PromptRenderer:
    def __init__(self) -> None:
        self._environment = Environment(
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

    def validate_contract(self, prompt: PromptDefinition) -> None:
        ast = self._environment.parse(prompt.template)
        referenced = meta.find_undeclared_variables(ast)
        declared = set(prompt.variables)
        undeclared = referenced - declared
        unused = declared - referenced
        if undeclared:
            raise PromptRenderError(
                f"Template references undeclared variables: {sorted(undeclared)}"
            )
        if unused:
            raise PromptRenderError(f"Declared variables are unused: {sorted(unused)}")

    def render(self, prompt: PromptDefinition, values: dict[str, Any]) -> str:
        self.validate_contract(prompt)
        unexpected = set(values) - set(prompt.variables)
        if unexpected:
            raise PromptRenderError(f"Unexpected variables: {sorted(unexpected)}")

        resolved: dict[str, Any] = {}
        for name, definition in prompt.variables.items():
            if name in values:
                value = values[name]
            elif definition.default is not None:
                value = definition.default
            elif definition.required:
                raise PromptRenderError(f"Missing required variable: {name}")
            else:
                value = None

            expected = _PYTHON_TYPES[definition.type]
            if definition.type == InputType.INTEGER and isinstance(value, bool):
                raise PromptRenderError(f"Variable {name!r} must be an integer")
            if definition.type == InputType.NUMBER and isinstance(value, bool):
                raise PromptRenderError(f"Variable {name!r} must be a number")
            if value is not None and not isinstance(value, expected):
                raise PromptRenderError(
                    f"Variable {name!r} must be {_TYPE_LABELS[definition.type]}; "
                    f"received {type(value).__name__}"
                )
            resolved[name] = value

        try:
            return self._environment.from_string(prompt.template).render(**resolved).strip()
        except TemplateError as exc:
            raise PromptRenderError(f"Template rendering failed: {exc}") from exc
