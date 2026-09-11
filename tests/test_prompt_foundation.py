from pathlib import Path

import pytest

from prompt_laboratory.loader import PromptLoadError, load_prompt
from prompt_laboratory.renderer import PromptRenderer, PromptRenderError

ROOT = Path(__file__).parents[1]
PROMPTS = sorted((ROOT / "prompts").glob("*/*.yaml"))


def test_all_cross_industry_prompts_load_and_have_unique_ids() -> None:
    loaded = [load_prompt(path) for path in PROMPTS]
    assert len(loaded) == 6
    assert len({prompt.id for prompt in loaded}) == len(loaded)
    assert {prompt.industry for prompt in loaded} == {
        "healthcare", "finance", "retail", "hr", "legal", "education"
    }


@pytest.mark.parametrize("path", PROMPTS, ids=lambda path: path.stem)
def test_all_prompt_contracts_are_consistent(path: Path) -> None:
    PromptRenderer().validate_contract(load_prompt(path))


def test_renderer_rejects_missing_and_unexpected_values() -> None:
    prompt = load_prompt(ROOT / "prompts/education/concept-explanation.yaml")
    renderer = PromptRenderer()

    with pytest.raises(PromptRenderError, match="Missing required variable"):
        renderer.render(prompt, {"concept": "gravity"})

    with pytest.raises(PromptRenderError, match="Unexpected variables"):
        renderer.render(
            prompt,
            {"concept": "gravity", "learning_level": "primary", "hidden": "value"},
        )


def test_renderer_checks_runtime_types() -> None:
    prompt = load_prompt(ROOT / "prompts/healthcare/patient-explanation.yaml")
    with pytest.raises(PromptRenderError, match="must be an integer"):
        PromptRenderer().render(
            prompt,
            {
                "patient_age": "twelve",
                "reading_level": "primary",
                "clinical_information": "A supplied statement.",
            },
        )


def test_renderer_produces_expected_text() -> None:
    prompt = load_prompt(ROOT / "prompts/education/concept-explanation.yaml")
    rendered = PromptRenderer().render(
        prompt,
        {"concept": "photosynthesis", "learning_level": "primary school"},
    )
    assert "photosynthesis" in rendered
    assert "primary school" in rendered


def test_loader_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("- not\n- a\n- prompt\n", encoding="utf-8")
    with pytest.raises(PromptLoadError, match="YAML mapping"):
        load_prompt(path)
