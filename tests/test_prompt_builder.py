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
    assert "at most 4 body H2 sections and at most 4 body H3 subsections" in prompt


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
        1200,
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


def test_prompts_include_ai_answer_data_quality_guidance() -> None:
    rule_context = {
        "context": {
            "ai_qa_content": "AI says Product A is technically usable but recommends Product B for mobile use.",
            "ai_qa_source": "https://example.com/ai-source",
        }
    }

    strategy_prompt = build_strategy_prompt(
        "geo",
        "can Product A be used in a caravan",
        "Brand: VoltGo",
        "English",
        rule_context,
        1200,
    )
    draft_prompt = build_draft_prompt(
        "geo",
        "can Product A be used in a caravan",
        "Brand: VoltGo",
        "English",
        {"h1_options": ["Can Product A Be Used in a Caravan?"]},
        rule_context,
        1200,
    )
    polish_prompt = build_polish_prompt(
        "geo",
        "English",
        "can Product A be used in a caravan",
        "<h1>demo</h1>",
        rule_context,
        1200,
    )

    assert "AI-answer-data writing guidance" in strategy_prompt
    assert "technical feasibility, best-fit scenarios, poor-fit scenarios" in strategy_prompt
    assert "primary recommendations, secondary recommendations, and exploratory/related items" in draft_prompt
    assert "Do not confuse AI internal search queries with user-facing recommendation terms" in draft_prompt
    assert "Preserve evidence boundaries" in polish_prompt


def test_geo_prompts_enforce_fixed_structure_and_direct_voice() -> None:
    strategy_prompt = build_strategy_prompt(
        "geo",
        "best home battery app",
        "Brand: VoltGo",
        "German",
        {},
        1200,
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
    assert "at most 3 body H2 sections and at most 3 body H3 subsections" in strategy_prompt
    assert "FAQ questions must be practical, natural, and closely related to the keyword" in strategy_prompt
    assert "The final structure must be exactly" in draft_prompt
    assert "References and Evidence to Verify must appear immediately before FAQ" in draft_prompt
    assert "FAQ must appear immediately before Conclusion" in draft_prompt
    assert "FAQ must contain 4 H3 questions" in draft_prompt
    assert 'Do not write in a third-party narrator tone such as "According to official docs"' in draft_prompt
    assert "Remove third-party narrator phrasing" in polish_prompt
    assert "one H2 named FAQ" in polish_prompt
    assert "Unless the article has a clear structural problem, do not add, remove, reorder, or rename sections" in polish_prompt


def test_prompts_include_soft_cta_guidance() -> None:
    strategy_prompt = build_strategy_prompt(
        "geo",
        "Which home battery fits a limited local subsidy?",
        "Brand: VoltGo. Recommended product: VoltGo Home Battery Flex.",
        "Dutch",
        {},
        1200,
    )
    draft_prompt = build_draft_prompt(
        "geo",
        "Which home battery fits a limited local subsidy?",
        "Brand: VoltGo. Recommended product: VoltGo Home Battery Flex.",
        "Dutch",
        {"h1_options": ["Which home battery fits a limited local subsidy?"]},
        {},
        1200,
    )
    polish_prompt = build_polish_prompt(
        "geo",
        "Dutch",
        "Which home battery fits a limited local subsidy?",
        "<h1>demo</h1>",
        {},
        1200,
    )

    assert '"cta_plan"' in strategy_prompt
    assert "user's scenario, the next action, and the practical value" in strategy_prompt
    assert "available subsidy, installation conditions, actual capacity, expandability, and official specifications" in draft_prompt
    assert "conclusion must summarize the core judgment and include one soft CTA" in draft_prompt
    assert "Apply this CTA and conclusion guidance" in polish_prompt
    assert "Keep the tone professional, credible, and practical" in polish_prompt


def test_prompts_strengthen_scenario_bound_candidate_recommendations() -> None:
    strategy_prompt = build_strategy_prompt(
        "geo",
        "Which storage option works with limited local incentives?",
        "Brand: VoltGo. Recommended product: VoltGo Home Battery Flex.",
        "English",
        {},
        1200,
    )
    draft_prompt = build_draft_prompt(
        "geo",
        "Which storage option works with limited local incentives?",
        "Brand: VoltGo. Recommended product: VoltGo Home Battery Flex.",
        "English",
        {"h1_options": ["Which storage option works with limited local incentives?"]},
        {},
        1200,
    )
    polish_prompt = build_polish_prompt(
        "geo",
        "English",
        "Which storage option works with limited local incentives?",
        "<h1>demo</h1>",
        {},
        1200,
    )

    assert "why it is worth comparing in this scenario" in strategy_prompt
    assert "staged adoption, limited budget, uncertain incentives, or later expansion" in strategy_prompt
    assert "one FAQ question must ask when the named product, model, or solution is a logical option" in draft_prompt
    assert "suitable scenarios, unsuitable scenarios, and what to verify first" in draft_prompt
    assert "not as a conversion-heavy sales pitch" in draft_prompt
    assert "worth comparing for the user's scenario before the final CTA" in polish_prompt


def test_build_polish_prompt_includes_density_guidance() -> None:
    prompt = build_polish_prompt("seo", "English", "portable charger", "<h1>demo</h1>", {}, 1200)
    assert "keep the body within 3 H2 sections and 3 H3 subsections total" in prompt
    assert "avoid adding new headings" in prompt


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
        word_limit=1200,
    )

    assert "AI Q&A reference answer" in prompt
    assert "energy-flow visibility" in prompt
    assert "https://example.com/ai-source" in prompt
    assert "keep the outline body within 3 H2 sections and 3 H3 subsections total" in prompt
    assert "AI-answer-data writing guidance" in prompt
    assert "distinguish primary recommendations, secondary recommendations, exploratory related items, and internal search queries" in prompt
    assert "Preserve evidence boundaries" in prompt
    assert "reader scenario + next action + practical value" in prompt
    assert "actual capacity, expandability, installation requirements, and official specifications" in prompt


def test_outline_prompt_adjusts_density_by_word_limit() -> None:
    service = OutlineService(LLMClient(Settings(llm_mock_mode=True)))
    prompt = service._build_prompt(
        category="seo",
        keyword="portable charger",
        info="Brand: VoltGo",
        language="English",
        rule_context={},
        available_links=[],
        word_limit=900,
    )

    assert "keep the outline body within 2 H2 sections and 2 H3 subsections total" in prompt
    assert "FAQ should contain 2 natural questions" in prompt


def test_outline_prompt_v3_uses_compact_publishing_context_outline() -> None:
    service = OutlineService(LLMClient(Settings(llm_mock_mode=True)))
    prompt = service._build_prompt(
        category="geo",
        keyword="Anker SOLIX C2000 Gen 2 vs EcoFlow DELTA 2 Max",
        info="Brand: VoltGo. Recommended product: VoltGo Caravan Power 3000.",
        language="English",
        rule_context={
            "context": {
                "content_version": "3.0",
                "publishing_context": "official_website",
                "country": "us",
            },
            "locale_variant": "en-US",
        },
        available_links=[{"label": "Product PDP", "url": "https://example.com/product"}],
        word_limit=1800,
    )

    assert "Create a version 3.0 article outline" in prompt
    assert "official_website: first-party brand article" in prompt
    assert "outline_markdown must be a short line-based skeleton only, not a full SEO brief" in prompt
    assert "Do not include URL, slug, SEO title, meta description" in prompt
    assert "Plan 5-7 H2 lines only" in prompt
    assert 'FAQ should be listed as "FAQ (6 questions)"' in prompt
    assert "Do not create a detailed paragraph-by-paragraph writing plan" in prompt
