from __future__ import annotations

from typing import Any

from app.services.prompt_store import get_prompt_store


MODE_TYPE_KEYWORD = 1
MODE_TYPE_OUTLINE = 2

PUBLISHING_CONTEXTS = ("official_website", "third_party_media", "conversion_page")


def _normalize_mode_type(mode_type: int) -> int:
    return MODE_TYPE_OUTLINE if int(mode_type) == MODE_TYPE_OUTLINE else MODE_TYPE_KEYWORD


def _body_structure_limits(word_limit: int) -> dict[str, int]:
    normalized_limit = max(200, int(word_limit))
    if normalized_limit <= 1000:
        return {"max_h2": 2, "max_h3": 2, "faq_count": 2}
    if normalized_limit <= 1400:
        return {"max_h2": 3, "max_h3": 3, "faq_count": 4}
    if normalized_limit <= 1800:
        return {"max_h2": 4, "max_h3": 4, "faq_count": 4}
    return {"max_h2": 5, "max_h3": 5, "faq_count": 5}


def _word_count_instructions(word_limit: int, limits: dict[str, int]) -> tuple[str, str]:
    """Return (draft_instruction, polish_instruction) for word count enforcement."""
    store = get_prompt_store()
    floor = int(word_limit * 0.90)
    ceiling = int(word_limit * 1.10)
    total_parts = limits["max_h2"] + 4
    per_section = max(80, word_limit // total_parts)
    draft = store.render(
        "shared.word_count.draft",
        word_limit=word_limit,
        floor=floor,
        ceiling=ceiling,
        per_section=per_section,
        per_section_max=per_section + 40,
    )
    polish = store.render(
        "shared.word_count.polish",
        word_limit=word_limit,
        floor=floor,
        ceiling=ceiling,
    )
    return draft, polish


def _get_section_names(language: str) -> dict[str, str]:
    """Return localized names for fixed GEO article sections based on target language."""
    lang = language.lower()
    if any(kw in lang for kw in ("dutch", "nl", "nederlands", "netherlands")):
        return {
            "quick_answer_prefix": "Kort antwoord",
            "references": "Bronnen en controlepunten",
            "faq": "Veelgestelde vragen",
            "conclusion": "Conclusie",
        }
    if any(kw in lang for kw in ("chinese", "zh", "mandarin", "中文", "简体", "繁體", "繁体")):
        return {
            "quick_answer_prefix": "简要回答",
            "references": "参考来源与验证要点",
            "faq": "常见问题",
            "conclusion": "结论",
        }
    # Default: English
    return {
        "quick_answer_prefix": "Quick Answer",
        "references": "References and Evidence to Verify",
        "faq": "FAQ",
        "conclusion": "Conclusion",
    }


def _strict_language_note(language: str) -> str:
    """Return a strict language-purity warning for non-English targets."""
    if language.lower() in ("english", "en"):
        return ""
    return get_prompt_store().render("shared.strict_language", language=language)


def _strict_language_line(language: str) -> str:
    note = _strict_language_note(language)
    return f"- {note}" if note else ""


def _build_rule_brief(rule_context: dict[str, Any]) -> str:
    context = rule_context.get("context", {})
    notes = [
        f"- Locale variant: {rule_context.get('locale_variant') or 'default'}",
        f"- Required sections: {', '.join(rule_context.get('required_sections') or []) or 'none'}",
        f"- Writing goals: {', '.join(rule_context.get('writing_goals') or []) or 'none'}",
    ]
    if context.get("country"):
        notes.append(f"- Country: {context['country']}")
    if context.get("market"):
        notes.append(f"- Market: {context['market']}")
    if context.get("article_type"):
        notes.append(f"- Article type: {context['article_type']}")
    if context.get("product_line"):
        notes.append(f"- Product line: {context['product_line']}")
    if context.get("topic_flags"):
        notes.append(f"- Topic flags: {', '.join(context['topic_flags'])}")
    if context.get("ai_qa_content"):
        notes.append(f"- AI Q&A reference answer: {context['ai_qa_content']}")
    if context.get("ai_qa_source"):
        notes.append(f"- AI Q&A adopted source links: {context['ai_qa_source']}")
    if rule_context.get("required_disclaimer"):
        notes.append("- A disclaimer block is mandatory for this article.")
    if rule_context.get("requires_shopify_link"):
        notes.append("- Add an internal product-page link within the first two paragraphs when a URL is provided.")
    if rule_context.get("resolved_internal_links"):
        links = "; ".join(f"{item['label']} -> {item['url']}" for item in rule_context["resolved_internal_links"][:3])
        notes.append(f"- Preferred internal links: {links}")
    if rule_context.get("required_notes"):
        notes.append(f"- Compliance notes: {'; '.join(rule_context['required_notes'])}")
    if rule_context.get("image_notes"):
        notes.append(f"- Image notes: {'; '.join(rule_context['image_notes'])}")
    if rule_context.get("banned_terms"):
        banned = ", ".join(rule_context["banned_terms"].keys())
        notes.append(f"- Avoid banned terms: {banned}")
    return "\n".join(notes)


def _ai_answer_data_guidance(category: str) -> str:
    store = get_prompt_store()
    suffix = "geo" if category == "geo" else "seo"
    return f"{store.render('shared.ai_answer_data.base')}\n\n{store.render(f'shared.ai_answer_data.{suffix}')}"


def _cta_guidance(category: str) -> str:
    store = get_prompt_store()
    suffix = "geo" if category == "geo" else "seo"
    return f"{store.render('shared.cta.base')}\n\n{store.render(f'shared.cta.{suffix}')}"


def _publishing_context(rule_context: dict[str, Any]) -> str:
    context = rule_context.get("context") or {}
    publishing_context = str(context.get("publishing_context") or "official_website")
    return publishing_context if publishing_context in PUBLISHING_CONTEXTS else "official_website"


def _v3_publishing_guidance(rule_context: dict[str, Any]) -> str:
    context = rule_context.get("context") or {}
    if str(context.get("content_version") or "2.0") != "3.0":
        return ""
    store = get_prompt_store()
    return store.render(
        "shared.v3.guidance",
        publishing_note=store.render(f"shared.v3.{_publishing_context(rule_context)}"),
    )


def _competitor_policy(rule_context: dict[str, Any], *, scope: str) -> str:
    """Return the comparison/competitor-naming rule, conditioned on publishing context.

    For content version 3.0 the comparison-intent rule adapts to the publishing context:
    third_party_media may name and compare specific competing brands; conversion_page keeps
    the focus on the primary product but may compare on objective criteria; official_website
    (and every other case, including version 2.0) suppresses competitor names. ``scope`` is
    "strategy" or "draft".
    """
    context = rule_context.get("context") or {}
    is_v3 = str(context.get("content_version") or "2.0") == "3.0"
    publishing_context = _publishing_context(rule_context)
    variant = (
        publishing_context
        if is_v3 and publishing_context in ("third_party_media", "conversion_page")
        else "default"
    )
    return get_prompt_store().render(f"shared.competitor.{variant}.{scope}")


def _mode_context(stage: str, mode_type: int, keyword: str, info: str) -> str:
    variant = "outline" if _normalize_mode_type(mode_type) == MODE_TYPE_OUTLINE else "keyword"
    return get_prompt_store().render(
        f"shared.context.{stage}.{variant}",
        keyword=keyword,
        info=info or "None provided.",
    )


def _mode_requirements(stage: str, mode_type: int) -> str:
    if _normalize_mode_type(mode_type) != MODE_TYPE_OUTLINE:
        return ""
    return get_prompt_store().render(f"shared.mode2.{stage}")


def build_strategy_prompt(
    category: str,
    keyword: str,
    info: str,
    language: str,
    rule_context: dict[str, Any] | None = None,
    word_limit: int = 1200,
    mode_type: int = MODE_TYPE_KEYWORD,
) -> str:
    limits = _body_structure_limits(word_limit)
    sec = _get_section_names(language)
    return get_prompt_store().render(
        "strategy.geo" if category == "geo" else "strategy.seo",
        mode_context=_mode_context("strategy", mode_type, keyword, info),
        rule_brief=_build_rule_brief(rule_context or {}),
        ai_answer_guidance=_ai_answer_data_guidance(category),
        cta_guidance=_cta_guidance(category),
        v3_guidance=_v3_publishing_guidance(rule_context or {}),
        competitor_policy=_competitor_policy(rule_context or {}, scope="strategy"),
        language=language,
        strict_language_line=_strict_language_line(language),
        quick_answer_prefix=sec["quick_answer_prefix"],
        references_heading=sec["references"],
        faq_heading=sec["faq"],
        conclusion_heading=sec["conclusion"],
        word_limit=word_limit,
        max_h2=limits["max_h2"],
        max_h3=limits["max_h3"],
        faq_count=limits["faq_count"],
        mode_requirements=_mode_requirements("strategy", mode_type),
    )


def build_draft_prompt(
    category: str,
    keyword: str,
    info: str,
    language: str,
    strategy: dict,
    rule_context: dict[str, Any] | None = None,
    word_limit: int = 1200,
    mode_type: int = MODE_TYPE_KEYWORD,
) -> str:
    limits = _body_structure_limits(word_limit)
    sec = _get_section_names(language)
    draft_word_instruction, _polish_word_instruction = _word_count_instructions(word_limit, limits)
    return get_prompt_store().render(
        "draft.geo" if category == "geo" else "draft.seo",
        language=language,
        mode_context=_mode_context("draft", mode_type, keyword, info),
        strategy_json=strategy,
        rule_brief=_build_rule_brief(rule_context or {}),
        ai_answer_guidance=_ai_answer_data_guidance(category),
        cta_guidance=_cta_guidance(category),
        v3_guidance=_v3_publishing_guidance(rule_context or {}),
        competitor_policy=_competitor_policy(rule_context or {}, scope="draft"),
        strict_language_line=_strict_language_line(language),
        keyword=keyword,
        quick_answer_prefix=sec["quick_answer_prefix"],
        references_heading=sec["references"],
        faq_heading=sec["faq"],
        conclusion_heading=sec["conclusion"],
        word_count_instruction=draft_word_instruction,
        max_h2=limits["max_h2"],
        max_h3=limits["max_h3"],
        faq_count=limits["faq_count"],
        mode_requirements=_mode_requirements("draft", mode_type),
    )


def build_polish_prompt(
    category: str,
    language: str,
    keyword: str,
    html: str,
    rule_context: dict[str, Any] | None = None,
    word_limit: int = 1200,
    mode_type: int = MODE_TYPE_KEYWORD,
) -> str:
    store = get_prompt_store()
    limits = _body_structure_limits(word_limit)
    sec = _get_section_names(language)
    _draft_word_instruction, polish_word_instruction = _word_count_instructions(word_limit, limits)
    variant = "geo" if category == "geo" else "seo"
    strict_line = _strict_language_line(language)
    geo_requirements = (
        store.render(
            "polish.geo_requirements",
            quick_answer_prefix=sec["quick_answer_prefix"],
            references_heading=sec["references"],
            faq_heading=sec["faq"],
            conclusion_heading=sec["conclusion"],
            faq_count=limits["faq_count"],
            strict_language_line=strict_line or f"- {store.render('shared.language_mix_fallback')}",
        )
        if category == "geo"
        else ""
    )
    topic_variant = "outline" if _normalize_mode_type(mode_type) == MODE_TYPE_OUTLINE else "keyword"
    return store.render(
        "polish.main",
        flavor=store.render(f"polish.flavor.{variant}"),
        structure_requirement=store.render(f"polish.structure.{variant}"),
        language=language,
        strict_language_line=strict_line,
        topic_requirement=store.render(f"polish.topic.{topic_variant}", keyword=keyword),
        word_count_instruction=polish_word_instruction,
        max_h2=limits["max_h2"],
        max_h3=limits["max_h3"],
        rule_brief=_build_rule_brief(rule_context or {}),
        ai_answer_guidance=_ai_answer_data_guidance(category),
        cta_guidance=_cta_guidance(category),
        v3_guidance=_v3_publishing_guidance(rule_context or {}),
        geo_requirements=geo_requirements,
        mode_requirement=_mode_requirements("polish", mode_type),
        html=html,
    )
