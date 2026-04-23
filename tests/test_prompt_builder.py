from app.services.prompt_builder import build_draft_prompt, build_polish_prompt


def test_build_draft_prompt_includes_word_limit() -> None:
    prompt = build_draft_prompt(
        "seo",
        "portable charger",
        "Brand: VoltGo",
        "English",
        {"h1_options": ["Portable Charger Guide"]},
        {},
        1800,
    )
    assert "1800" in prompt
    assert "excluding any image content" in prompt


def test_build_polish_prompt_includes_word_limit() -> None:
    prompt = build_polish_prompt("geo", "English", "portable charger", "<h1>demo</h1>", {}, 1400)
    assert "1400" in prompt
    assert "excluding image content" in prompt


def test_build_draft_prompt_in_outline_mode_requires_strict_structure() -> None:
    prompt = build_draft_prompt(
        "seo",
        "# Portable Charger Guide\n## Airline rules\n## Battery limits",
        "Brand: VoltGo",
        "English",
        {"h1_options": ["Portable Charger Guide"]},
        {},
        1200,
        2,
    )
    assert "Follow the provided outline strictly" in prompt
    assert "Outline from keyword field" in prompt
    assert "Brand/Product info: Brand: VoltGo" in prompt
