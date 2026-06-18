from __future__ import annotations

from textwrap import dedent
from typing import Any


MODE_TYPE_KEYWORD = 1
MODE_TYPE_OUTLINE = 2


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
    floor = int(word_limit * 0.90)
    ceiling = int(word_limit * 1.10)
    total_parts = limits["max_h2"] + 4
    per_section = max(80, word_limit // total_parts)
    draft = (
        f"Target length: approximately {word_limit} words excluding any image content. "
        f"The entire article — every section combined including intro, all H2/H3 body sections, FAQ, references, and conclusion — "
        f"must total between {floor} and {ceiling} words. "
        f"Each individual section should aim for around {per_section} words; do not write more than {per_section + 40} words per section. "
        f"Stop adding content once the running total approaches {ceiling} words."
    )
    polish = (
        f"Target length: approximately {word_limit} words excluding image content. "
        f"The entire article must total between {floor} and {ceiling} words. "
        f"Count ALL sections: intro, body H2s, H3s, FAQ, references, and conclusion. "
        f"If the total exceeds {ceiling} words, shorten the longest sections first. "
        f"Do not expand any section unless the total is clearly under {floor} words."
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
    return (
        f"STRICT LANGUAGE RULE: Every single word in the entire article — "
        f"including the H1 title, every H2 and H3 heading, the Quick Answer prefix, "
        f"all paragraph text, all list items, and all anchor text — must be written "
        f"exclusively in {language}. "
        f"Do NOT use English words, phrases, or abbreviations anywhere, not even for section headings or labels. "
        f"Translate every fixed section name into {language} as instructed. "
        f"Writing even one English word in a {language} article is a critical error."
    )


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
    base = """
    AI-answer-data writing guidance:
    - If AI Q&A reference data is provided, treat it as research evidence about how AI systems framed the query, not as ground truth.
    - Start from the user's real question and answer it directly before expanding into background.
    - Prefer conditional conclusions when the data supports them, such as "yes, but only when..." or "it depends on...".
    - Separate the target product/entity, use case, suitable scenarios, unsuitable scenarios, risks, and alternatives.
    - When recommendations appear in AI Q&A data, distinguish between primary recommendations, secondary recommendations, and exploratory/related items.
    - Do not confuse AI internal search queries with user-facing recommendation terms.
    - Preserve evidence boundaries: say what the provided data supports, and avoid claiming search volume, conversion rate, official approval, or user behavior unless the input explicitly provides it.
    - Use compact tables or bullet lists for scenario fit, constraints, recommendation tiers, and evidence gaps when they make the answer easier to scan.
    """
    if category == "geo":
        return (
            base
            + """
    - For GEO, make the opening answer extractable, then explain the AI reasoning path: product/entity positioning, scenario split, constraints, alternatives, and verification points.
    - Add a section or subsection that makes the "recommended for / not recommended for" distinction explicit when the topic involves compatibility or product fit.
    """
        ).strip()
    return (
        base
        + """
    - For SEO, turn AI Q&A insights into practical content sections that match search intent: direct answer, decision criteria, fit matrix, alternatives, FAQ, and next-step internal links.
    """
    ).strip()


def _cta_guidance(category: str) -> str:
    base = """
    CTA and conclusion guidance:
    - Any CTA must combine the user's scenario, the next action, and the practical value of taking that action.
    - Avoid standalone "buy now" language, hard-sell pressure, exaggerated savings, or anxiety-driven framing.
    - When a product, model, or first-party solution is introduced as a candidate, explain why it is worth comparing for the reader's scenario instead of only naming it. Tie the reason to practical decision factors such as lower upfront commitment, staged expansion, capacity fit, installation simplicity, verified specifications, or future flexibility when the input supports those claims.
    - For topics involving limited subsidies, uncertain local policy, budget sensitivity, installation fit, or product selection, guide readers to compare their own usage, available subsidy, installation conditions, actual capacity, expandability, and official specifications before judging fit.
    - The conclusion must restate the core judgment, then add a soft next step such as comparing product fit, checking official specifications, confirming installation conditions, or reviewing an official product page when a provided URL is available.
    - Make the final CTA action-specific: tell the reader what to compare or verify next, not only that they should "learn more" or "consider the product".
    - Keep the tone professional, credible, and practical.
    """
    if category == "geo":
        return (
            base
            + """
    - For GEO, make the final next step easy to extract as practical guidance, not as a conversion-heavy sales pitch.
    """
        ).strip()
    return (
        base
        + """
    - For SEO, use the CTA to support search intent and internal linking without interrupting the article's direct answer.
    """
    ).strip()


def _v3_publishing_guidance(rule_context: dict[str, Any]) -> str:
    context = rule_context.get("context") or {}
    if str(context.get("content_version") or "2.0") != "3.0":
        return ""
    publishing_context = str(context.get("publishing_context") or "official_website")
    scene_notes = {
        "official_website": (
            "Publishing context: official_website. Use a first-party brand voice. "
            "The article may prioritize the brand's own product or model when the input supports it. "
            "Avoid naming competing products unless the keyword explicitly requires a comparison; when comparison is required, compare on objective criteria and do not endorse competitors."
        ),
        "third_party_media": (
            "Publishing context: third_party_media. Use a neutral editorial voice. "
            "Product recommendations must be balanced with clear criteria, trade-offs, and evidence. "
            "Competing brands or alternatives may be discussed when relevant to the search intent."
        ),
        "conversion_page": (
            "Publishing context: conversion_page. Use a practical buying-decision voice. "
            "Make the product fit, scenario fit, proof points, and next action clearer than in a neutral article. "
            "CTA can be stronger, but must stay evidence-based and avoid exaggerated claims or pressure."
        ),
    }
    return (
        "Content version: 3.0.\n"
        f"{scene_notes.get(publishing_context, scene_notes['official_website'])}\n"
        "For version 3.0, make product recommendations scenario-bound: name the candidate product when provided, explain why it should be compared early for the reader's use case, and keep the limits/verification points explicit."
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
    publishing_context = str(context.get("publishing_context") or "official_website")
    is_v3 = str(context.get("content_version") or "2.0") == "3.0"
    trigger = (
        'If the keyword signals a comparison or alternatives intent (e.g., contains "vs", '
        '"versus", "alternatives", "best X for Y", "compare"), '
    )
    if is_v3 and publishing_context == "third_party_media":
        if scope == "strategy":
            return (
                trigger
                + "plan a balanced comparison that may name specific competing brands or products; "
                "give each candidate clear criteria, trade-offs, and evidence, and do not default to a single-brand recommendation"
            )
        return (
            trigger
            + "you may name and compare specific competing brands or products in the article body; "
            "keep the comparison balanced with clear criteria, trade-offs, and evidence, and do not collapse it into a single-brand recommendation"
        )
    if is_v3 and publishing_context == "conversion_page":
        if scope == "strategy":
            return (
                trigger
                + "keep the comparison centered on the primary/named product and the reader's buying decision; "
                "you may contrast it against alternative categories or objective criteria, but do not recommend or promote specific competing brands as the better choice; keep claims evidence-based without pressure"
            )
        return (
            trigger
            + "keep the article body centered on the primary/named product and the reader's buying decision; "
            "you may compare on objective criteria, fit, and proof points, but do not name competing brands as recommended alternatives; keep the CTA evidence-based and free of exaggerated claims or pressure"
        )
    if scope == "strategy":
        return (
            trigger
            + "do not recommend or name specific competing brands or products in the outline or writing suggestions; "
            "compare based on neutral criteria, use-case fit, and objective specifications instead"
        )
    return (
        trigger
        + "do not name or recommend specific competing brands or products anywhere in the article body; "
        "compare only on neutral criteria, use-case fit, and objective specifications"
    )


def build_strategy_prompt(
    category: str,
    keyword: str,
    info: str,
    language: str,
    rule_context: dict[str, Any] | None = None,
    word_limit: int = 1200,
    mode_type: int = MODE_TYPE_KEYWORD,
) -> str:
    rule_brief = _build_rule_brief(rule_context or {})
    ai_answer_guidance = _ai_answer_data_guidance(category)
    cta_guidance = _cta_guidance(category)
    v3_guidance = _v3_publishing_guidance(rule_context or {})
    competitor_policy = _competitor_policy(rule_context or {}, scope="strategy")
    normalized_mode_type = _normalize_mode_type(mode_type)
    limits = _body_structure_limits(word_limit)
    sec = _get_section_names(language)
    strict_lang = _strict_language_note(language)
    mode_context = (
        f"""
        Provided outline from the keyword field:
        {keyword}

        Brand or product information:
        {info or "None provided."}
        """
        if normalized_mode_type == MODE_TYPE_OUTLINE
        else f"""
        Keyword:
        {keyword}

        Brand or product information:
        {info or "None provided."}
        """
    )
    mode_requirements = (
        """
            - mode_type=2 means the keyword field contains the required outline, not a short SEO keyword
            - Preserve the outline hierarchy, heading order, and section intent from the keyword field
            - Do not invent extra H2/H3 sections unless a minimal structural repair is required
            - If the outline contains an H1, use it as the primary H1 option
            - Use the brand/product info only as supporting context inside the provided outline
        """
        if normalized_mode_type == MODE_TYPE_OUTLINE
        else ""
    )
    if category == "seo":
        return dedent(
            f"""
            You are a senior SEO content strategist.
            Create a writing strategy for the requested article.

            {mode_context}

            Rule context:
            {rule_brief}

            {ai_answer_guidance}

            {cta_guidance}

            {v3_guidance}

            Return strict JSON only:
            {{
              "intent": "",
              "audience": "",
              "meta_title": "",
              "meta_description": "",
              "h1_options": ["", "", ""],
              "outline": [
                {{"level": "H2", "title": ""}},
                {{"level": "H3", "title": ""}}
              ],
              "longtail_keywords": ["", "", "", ""],
              "faq_questions": ["", "", ""],
              "image_briefs": ["", ""],
              "link_opportunities": ["", ""],
              "compliance_notes": ["", ""],
              "internal_link_plan": [
                {{"label": "", "placement": "", "url_hint": ""}}
              ],
              "cta_plan": {{
                "reader_scenario": "",
                "next_action": "",
                "value": "",
                "conclusion_angle": ""
              }}
            }}

            Requirements:
            - All output must be written in {language}
            {f"- {strict_lang}" if strict_lang else ""}
            - Follow SEO blog rules:
              1. Meta title should stay within 60 characters
              2. Meta description should stay within 160 characters
              3. Use exactly one H1
              4. Structure should be H1, introduction, H2/H3 body, conclusion, FAQ
              5. FAQ should contain {limits["faq_count"]} natural follow-up questions for this target length
              6. When brand/product info is provided, include one FAQ question that captures product or solution fit, such as when the named option is a logical choice and when extra checking is needed
              7. Titles should reflect the core topic naturally
            - Outline should target approximately {word_limit} words/characters of textual content
            - HARD LIMIT: the outline must contain no more than {limits["max_h2"]} body H2 sections — combine related subtopics into fewer sections rather than adding more H2s
            - HARD LIMIT: use no more than {limits["max_h3"]} body H3 subsections in total
            - In plain terms: use at most {limits["max_h2"]} body H2 sections and at most {limits["max_h3"]} body H3 subsections
            - Only use H3 when it materially improves clarity; do not add H3 by default
            - Each body H2 section should be concise — plan for one to two short paragraphs per section, not multi-paragraph deep dives
            - Headings should be specific, benefit-driven, and not generic
            - Link opportunities should describe relevant anchor ideas and use provided URLs only when available
            - Internal link plan should call out the best early-link placement when rule context requires it
            - Build cta_plan around the reader's scenario, the next action they should take, and the value they gain from that action
            - If a product or solution is a candidate recommendation, plan one sentence explaining why it is worth comparing in this scenario, especially when staged adoption, limited budget, uncertain incentives, or later expansion affects the decision
            - Compliance notes should reflect disclaimers, compatibility notes, or banned-term constraints
            - Image briefs should describe helpful supporting visuals and mention topic placement advice
            - {competitor_policy}
            {mode_requirements}
            """
        ).strip()

    return dedent(
        f"""
        You are a GEO content strategist focused on AI citability and answer extraction.
        Create a writing strategy for the requested article.

        {mode_context}

        Rule context:
        {rule_brief}

        {ai_answer_guidance}

        {cta_guidance}

        {v3_guidance}

        Return strict JSON only:
        {{
          "search_intent": "",
          "audience": "",
          "meta_title": "",
          "meta_description": "",
          "answer_first_summary": "",
          "entity_summary": "",
          "h1_options": ["", "", ""],
          "outline": [
            {{"level": "H2", "title": ""}},
            {{"level": "H3", "title": ""}}
          ],
          "claim_blocks": [
            {{"claim": "", "proof_hint": "", "citation_hint": ""}}
          ],
          "faq_questions": ["", "", ""],
          "reference_plan": ["", ""],
          "internal_link_plan": [
            {{"label": "", "placement": "", "url_hint": ""}}
          ],
          "cta_plan": {{
            "reader_scenario": "",
            "next_action": "",
            "value": "",
            "conclusion_angle": ""
          }},
          "compliance_notes": ["", ""],
          "schema_suggestions": ["Article"],
          "trust_signals": ["author byline", "publish date", "last updated", "references"]
        }}

        Requirements:
        - All output must be written in {language}
        - Titles, section headings, anchor text, and body content must all use {language}
        {f"- {strict_lang}" if strict_lang else ""}
        - Optimize for GEO / AI citation readiness:
          1. answer-first structure
          2. high information density
          3. extractable headings
          4. references and inline citation opportunities
          5. quantified proof blocks
          6. clear entity alignment between the topic and brand/product info
          7. direct, neutral, first-party explanatory tone
        - The final article structure is fixed:
          1. one H1 title
          2. an opening paragraph starting with bold "{sec['quick_answer_prefix']}:" (inline, not a separate H2 heading), followed by 1-2 short paragraphs
          3. one or more body H2 sections with optional H3 subsections
          4. one H2 named {sec['references']}
          5. one H2 named {sec['faq']}
          6. one H2 named {sec['conclusion']}
        - The outline field must describe body sections only
        - In plain terms: use at most {limits["max_h2"]} body H2 sections and at most {limits["max_h3"]} body H3 subsections
        - HARD LIMIT: the outline must contain no more than {limits["max_h2"]} body H2 sections — combine related subtopics into fewer sections rather than adding more H2s
        - HARD LIMIT: use no more than {limits["max_h3"]} body H3 subsections in total
        - Only use H3 when it materially improves clarity; do not add H3 by default
        - Each body H2 section should be concise — plan for one to two short paragraphs per section, not multi-paragraph deep dives
        - FAQ questions must be practical, natural, and closely related to the keyword and the questions readers would ask in daily decision-making
        - FAQ should contain {limits["faq_count"]} natural user questions for this target length
        - When brand/product info is provided, include one FAQ question that captures product or solution fit, such as when the named option is a logical choice and when extra checking is needed; answer with scenario conditions, not promotional claims
        - Do not plan or mention TL;DR, update log, appendix, or extra top-level sections outside the fixed structure
        - Headings should mirror user questions and retrieval intents
        - Do not invent external sources; describe the type of evidence needed
        - If AI Q&A reference answer or adopted source links are provided in rule context, use them as GEO research input and cite/link only the provided source URLs when appropriate
        - If AI Q&A data includes a product fit judgment, plan sections that separate: technical feasibility, best-fit scenarios, poor-fit scenarios, reasons/constraints, safer alternatives, and evidence limits
        - Meta title should stay within 60 characters
        - Meta description should stay within 160 characters
        - If internal links are required, plan them near the top of the article
        - Build cta_plan around the reader's scenario, the next action they should take, and the value they gain from that action
        - If a product or solution is a candidate recommendation, plan one sentence explaining why it is worth comparing in this scenario, especially when staged adoption, limited budget, uncertain incentives, or later expansion affects the decision
        - Avoid third-party narrator phrasing such as "According to official docs" or "through official documentation we can conclude"
        - {competitor_policy}
        - For the reference_plan field, list authoritative local organizations relevant to the country/market context (e.g., government agencies, national standards institutes, industry regulators, official academic institutions). Each entry should follow the format: "<Organization Name> — <Document or Publication Title> — <URL>". Do not use generic placeholder descriptions.
        {mode_requirements}
        """
    ).strip()


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
    rule_brief = _build_rule_brief(rule_context or {})
    ai_answer_guidance = _ai_answer_data_guidance(category)
    cta_guidance = _cta_guidance(category)
    v3_guidance = _v3_publishing_guidance(rule_context or {})
    competitor_policy = _competitor_policy(rule_context or {}, scope="draft")
    normalized_mode_type = _normalize_mode_type(mode_type)
    limits = _body_structure_limits(word_limit)
    sec = _get_section_names(language)
    strict_lang = _strict_language_note(language)
    draft_word_instruction, _polish_word_instruction = _word_count_instructions(word_limit, limits)
    content_context = (
        f"""
            Outline from keyword field:
            {keyword}
            Brand/Product info: {info or "None provided."}
        """
        if normalized_mode_type == MODE_TYPE_OUTLINE
        else f"""
            Keyword: {keyword}
            Brand/Product info: {info or "None provided."}
        """
    )
    mode_requirements = (
        """
            - mode_type=2 means the keyword field is a required outline, not a short keyword
            - Follow the provided outline strictly: preserve heading order, heading levels, and section boundaries
            - Do not add, remove, rename, merge, or reorder headings unless the outline is malformed and needs a minimal repair
            - Keep SEO/GEO writing quality inside the provided outline instead of inventing a different structure
            - Use the brand/product info only as supporting facts, examples, proof, and entity context
        """
        if normalized_mode_type == MODE_TYPE_OUTLINE
        else ""
    )
    if category == "seo":
        return dedent(
            f"""
            You are a senior SEO article writer.
            Use the strategy below to write a complete HTML article.

            Language: {language}
            {content_context}
            Strategy JSON:
            {strategy}
            Rule context:
            {rule_brief}

            {ai_answer_guidance}

            {cta_guidance}

            {v3_guidance}

            Requirements:
            - Return pure HTML only
            - Use h1, h2, h3, p, ul, li, strong, a tags only
            - All visible text must be written in {language}
            {f"- {strict_lang}" if strict_lang else ""}
            - Structure:
              1. exact H1
              2. introduction that answers intent quickly
              3. H2/H3 body sections
              4. conclusion
              5. FAQ section with {limits["faq_count"]} natural follow-up questions
            - {draft_word_instruction}
            - HARD LIMIT: use exactly {limits["max_h2"]} body H2 sections maximum — do not add more H2 sections even if the topic seems to warrant it
            - HARD LIMIT: use at most {limits["max_h3"]} H3 subsections total across the entire article
            - In plain terms: use at most {limits["max_h2"]} body H2 sections and at most {limits["max_h3"]} body H3 subsections
            - Only use H3 when it materially improves clarity; do not add H3 by default
            - Each body H2 section should contain at most two short paragraphs; avoid long multi-paragraph sections
            - When mode_type=1, keep the main keyword naturally present in H1, intro, and conclusion
            - Paragraphs should stay compact and readable
            - When mode_type=1, use long-tail keywords naturally and never stuff them
            - If brand/product info is provided, integrate it naturally without turning the article into a sales page
            - When brand/product info is provided, include one FAQ question about when the named product, model, or solution is a logical option; answer with suitable scenarios, unsuitable scenarios, and what to verify first
            - When presenting any product or solution as a candidate, explain why it is worth comparing for this reader's scenario before asking the reader to take the next step
            - Use provided internal URLs when the strategy includes them; otherwise do not invent URLs
            - Respect all compliance notes, disclaimers, and compatibility constraints from the rule context
            - When AI Q&A data is present, include the distinction between what the AI answer recommends, what it only explores, and what cannot be inferred from the data
            - Use strategy.cta_plan when present; the conclusion must summarize the core judgment and include one soft CTA tied to the reader's scenario, next action, and practical value
            {mode_requirements}
            """
        ).strip()

    return dedent(
        f"""
        You are a GEO article writer focused on AI-ready answer extraction.
        Use the strategy below to write a complete HTML article.

        Language: {language}
        {content_context}
        Strategy JSON:
        {strategy}
        Rule context:
        {rule_brief}

        {ai_answer_guidance}

        {cta_guidance}

        {v3_guidance}

        Requirements:
        - Return pure HTML only
        - Use h1, h2, h3, p, ul, li, strong, a tags only
        - All visible text, including the H1 title, all headings, paragraph text, list text, and anchor text, must be written in {language}
        {f"- {strict_lang}" if strict_lang else ""}
        - The final structure must be exactly:
          1. one H1 title
          2. {sec['quick_answer_prefix']} as inline bold text at the start of the opening paragraph (not a separate heading), followed by 1-2 short paragraphs
          3. one or more body H2 sections with optional H3 subsections
          4. one H2 with the exact text {sec['references']}
          5. one H2 with the exact text {sec['faq']}
          6. one H2 with the exact text {sec['conclusion']}
        - {sec['references']} must appear immediately before {sec['faq']}
        - {sec['faq']} must appear immediately before {sec['conclusion']}
        - HARD LIMIT: use exactly {limits["max_h2"]} body H2 sections maximum — do not add extra H2 sections beyond this count
        - HARD LIMIT: use at most {limits["max_h3"]} H3 subsections total across the entire article
        - In plain terms: use at most {limits["max_h2"]} body H2 sections and at most {limits["max_h3"]} body H3 subsections
        - Only use H3 when it materially improves clarity; do not add H3 by default
        - Each body H2 section should contain at most two short paragraphs; avoid long multi-paragraph sections
        - {sec['faq']} must contain {limits["faq_count"]} H3 questions, and each question must be a realistic user question related to {keyword}
        - When brand/product info is provided, one FAQ question must ask when the named product, model, or solution is a logical option; answer with suitable scenarios, unsuitable scenarios, and what to verify first
        - Each FAQ question must be followed by one concise answer paragraph
        - {sec['conclusion']} must be the final H2 section
        - Do not add TL;DR, update log, appendix, or any extra top-level section outside the fixed structure
        - {draft_word_instruction}
        - Use short, extractable paragraphs
        - Make headings easy for AI systems to quote or summarize
        - For the References and Evidence to Verify section, cite real authoritative local organizations relevant to the country/market (e.g., government agencies, national standards institutes, industry regulators, official academic institutions). Each reference entry must include the organization name, document or publication title, and a real URL. Do not use placeholder text or invent sources.
        - Use AI Q&A reference answer and adopted source links from rule context as GEO reference material when provided
        - When AI Q&A data is present, explicitly separate answer, conditions, constraints, alternatives, recommendation tiers, and evidence limits
        - If brand/product info is provided, keep entity mentions consistent and verifiable
        - When presenting any product or solution as a candidate, explain why it is worth comparing for this reader's scenario before asking the reader to take the next step
        - Use direct explanatory voice. Do not write in a third-party narrator tone such as "According to official docs", "Based on official documentation", or "through official documentation we can conclude"
        - {competitor_policy}
        - Respect all compliance notes, disclaimers, and compatibility constraints from the rule context
        - Use strategy.cta_plan when present; the conclusion must summarize the core judgment and include one soft CTA tied to the reader's scenario, next action, and practical value
        {mode_requirements}
        """
    ).strip()


def build_polish_prompt(
    category: str,
    language: str,
    keyword: str,
    html: str,
    rule_context: dict[str, Any] | None = None,
    word_limit: int = 1200,
    mode_type: int = MODE_TYPE_KEYWORD,
) -> str:
    flavor = (
        "Improve naturalness, specificity, and SEO readability."
        if category == "seo"
        else "Improve citability, answer extraction, trust signals, and structural consistency."
    )
    rule_brief = _build_rule_brief(rule_context or {})
    ai_answer_guidance = _ai_answer_data_guidance(category)
    cta_guidance = _cta_guidance(category)
    v3_guidance = _v3_publishing_guidance(rule_context or {})
    sec = _get_section_names(language)
    strict_lang = _strict_language_note(language)
    normalized_mode_type = _normalize_mode_type(mode_type)
    topic_requirement = (
        'Keep the keyword "{keyword}" naturally present'.format(keyword=keyword)
        if normalized_mode_type == MODE_TYPE_KEYWORD
        else "Keep the article aligned to the supplied outline and preserve the heading wording intent"
    )
    structure_requirement = (
        "- Keep the existing HTML structure intact"
        if category == "seo"
        else "- Keep the existing structure and section order unless there is an obvious structural problem that must be repaired"
    )
    mode_requirement = (
        "- mode_type=2: keep the exact heading structure, order, and section boundaries from the current HTML"
        if normalized_mode_type == MODE_TYPE_OUTLINE
        else ""
    )
    density_notes = _body_structure_limits(word_limit)
    _draft_word_instruction, polish_word_instruction = _word_count_instructions(word_limit, density_notes)
    geo_requirements = (
        f"""
        - For GEO articles, the final structure must be exactly:
          1. one H1 title
          2. an opening paragraph starting with bold "{sec['quick_answer_prefix']}:" (inline, not a separate H2 heading), followed by 1-2 short paragraphs
          3. one or more body H2 sections with optional H3 subsections
          4. one H2 named {sec['references']}
          5. one H2 named {sec['faq']}
          6. one H2 named {sec['conclusion']} as the final section
        - {sec['faq']} must stay immediately before {sec['conclusion']} and contain {density_notes["faq_count"]} natural user questions related to the target keyword
        - If a named product, model, or solution appears, keep or add one natural FAQ that explains when it is a logical option and when extra verification is needed, without adding a new top-level section
        - Keep all headings and visible text in the requested language
        - {strict_lang if strict_lang else "Do not mix languages within the article."}
        - Unless the article has a clear structural problem, do not add, remove, reorder, or rename sections
        - Default to polishing wording, headings, clarity, and fluency rather than restructuring
        - Remove AI-sounding phrasing, generic filler, and robotic repetition so the article reads like it was written by a human writer
        - Remove third-party narrator phrasing such as "According to official docs", "Based on official documentation", "through official documentation we can conclude", or "通过官方文档可以得出"
        - State conclusions directly, then place source guidance in the references section
        - If the References and Evidence to Verify section contains placeholder text or invented sources, replace them with real authoritative local organizations (government agencies, national standards institutes, industry regulators, or official academic institutions), each with organization name, document/publication title, and a real URL
        - If the keyword signals a comparison or alternatives intent, ensure the article does not name or recommend specific competing brands; replace any competitor mentions with neutral criteria-based comparisons
        """
        if category == "geo"
        else ""
    )
    return dedent(
        f"""
        You are an expert editor.
        Rewrite the HTML article below to sound more human and more useful.

        Goals:
        - {flavor}
        - {structure_requirement.removeprefix("- ")}
        - Do not change the core meaning
        - Keep the article in {language}
        {f"- {strict_lang}" if strict_lang else ""}
        - {topic_requirement}
        - {polish_word_instruction}
        - HARD LIMIT: the article must have no more than {density_notes["max_h2"]} body H2 sections and {density_notes["max_h3"]} body H3 subsections — if the draft exceeds this, merge or remove the least essential sections
        - For this target length, keep the body within {density_notes["max_h2"]} H2 sections and {density_notes["max_h3"]} H3 subsections total; avoid adding new headings
        - Do not add new headings; shorten or merge existing sections to meet the word count limit
        - If the article names a product, model, or first-party solution, ensure the copy explains why it is worth comparing for the user's scenario before the final CTA
        - Make the final CTA action-specific by naming the comparison or verification dimensions the reader should check next
        - Keep compliance with the following rule context:
        {rule_brief}
        - Apply this AI-answer-data guidance where relevant:
        {ai_answer_guidance}
        - Apply this CTA and conclusion guidance where relevant:
        {cta_guidance}
        {v3_guidance}
        {geo_requirements}
        {mode_requirement}
        - Return HTML only

        Article:
        {html}
        """
    ).strip()
