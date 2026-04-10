from app.services.prompt_builder import build_draft_prompt, build_polish_prompt


def test_build_draft_prompt_includes_word_limit() -> None:
    prompt = build_draft_prompt(
        "seo",
        "portable charger",
        "Brand: VoltGo",
        "English",
        {"h1_options": ["Portable Charger Guide"]},
        1800,
    )
    assert "1800" in prompt
    assert "excluding any image content" in prompt


def test_build_polish_prompt_includes_word_limit() -> None:
    prompt = build_polish_prompt("geo", "English", "portable charger", "<h1>demo</h1>", 1400)
    assert "1400" in prompt
    assert "excluding image content" in prompt
