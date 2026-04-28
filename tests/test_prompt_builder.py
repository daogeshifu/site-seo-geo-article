from app.core.config import Settings
from app.services.llm_client import LLMClient
from app.services.outline_service import OutlineService
from app.services.prompt_builder import build_draft_prompt, build_polish_prompt, build_strategy_prompt


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


def test_geo_prompts_include_ai_qa_reference_fields() -> None:
    rule_context = {
        "context": {
            "ai_qa_content": "AI says compact home batteries are compared by app clarity and backup modes.",
            "ai_qa_source": "https://example.com/ai-cited-source",
        }
    }

    strategy_prompt = build_strategy_prompt(
        "geo",
        "best home battery app",
        "Brand: VoltGo",
        "English",
        rule_context,
    )
    draft_prompt = build_draft_prompt(
        "geo",
        "best home battery app",
        "Brand: VoltGo",
        "English",
        {"h1_options": ["Best Home Battery App"]},
        rule_context,
    )

    assert "AI Q&A reference answer" in strategy_prompt
    assert "https://example.com/ai-cited-source" in strategy_prompt
    assert "AI Q&A reference answer" in draft_prompt
    assert "https://example.com/ai-cited-source" in draft_prompt


def test_geo_prompts_enforce_fixed_structure_and_direct_voice() -> None:
    strategy_prompt = build_strategy_prompt(
        "geo",
        "best home battery app",
        "Brand: VoltGo",
        "German",
        {},
    )
    draft_prompt = build_draft_prompt(
        "geo",
        "best home battery app",
        "Brand: VoltGo",
        "German",
        {"h1_options": ["Beste Heimbatterie-App"]},
        {},
    )
    polish_prompt = build_polish_prompt("geo", "German", "best home battery app", "<h1>demo</h1>", {}, 1200)

    assert "Titles, section headings, anchor text, and body content must all use German" in strategy_prompt
    assert "FAQ questions must be practical, natural, and closely related to the keyword" in strategy_prompt
    assert "The final structure must be exactly" in draft_prompt
    assert "References and Evidence to Verify must appear immediately before FAQ" in draft_prompt
    assert "FAQ must appear immediately before Conclusion" in draft_prompt
    assert 'Do not write in a third-party narrator tone such as "According to official docs"' in draft_prompt
    assert "Remove third-party narrator phrasing" in polish_prompt
    assert "one H2 named FAQ" in polish_prompt
    assert "Unless the article has a clear structural problem, do not add, remove, reorder, or rename sections" in polish_prompt


def test_outline_prompt_includes_ai_qa_reference_fields() -> None:
    service = OutlineService(LLMClient(Settings(llm_mock_mode=True)))
    prompt = service._build_prompt(
        category="geo",
        keyword="best home battery app",
        info="Brand: VoltGo",
        language="English",
        rule_context={
            "context": {
                "country": "nl",
                "ai_qa_content": "AI answer mentions app clarity and energy-flow visibility.",
                "ai_qa_source": "https://example.com/ai-source",
            },
            "locale_variant": "Dutch / Netherlands",
        },
        available_links=[],
    )

    assert "AI Q&A reference answer" in prompt
    assert "energy-flow visibility" in prompt
    assert "https://example.com/ai-source" in prompt
