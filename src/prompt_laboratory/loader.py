"""Safe YAML loading with actionable validation errors."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from prompt_laboratory.models import PromptDefinition


class PromptLoadError(ValueError):
    """Raised when a prompt file cannot be parsed or validated."""


def load_prompt(path: str | Path) -> PromptDefinition:
    prompt_path = Path(path)
    try:
        raw: Any = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PromptLoadError(f"Cannot read prompt file {prompt_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise PromptLoadError(f"Invalid YAML in {prompt_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PromptLoadError(f"Prompt file {prompt_path} must contain a YAML mapping")

    try:
        return PromptDefinition.model_validate(raw)
    except ValidationError as exc:
        raise PromptLoadError(f"Invalid prompt definition in {prompt_path}:\n{exc}") from exc
