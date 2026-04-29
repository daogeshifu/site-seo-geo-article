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
        return {"max_h2": 3, "max_h3": 3, "faq_count": 2}
    if normalized_limit <= 1800:
        return {"max_h2": 4, "max_h3": 4, "faq_count": 3}
    return {"max_h2": 5, "max_h3": 5, "faq_count": 4}


def _word_count_instructions(word_limit: int, limits: dict[str, int]) -> tuple[str, str]:
    """Return (draft_instruction, polish_instruction) for word count enforcement."""
    floor = int(word_limit * 0.95)
    per_section = max(80, word_limit // (limits["max_h2"] + 2))
    draft = (
        f"You must write at least {floor} words of textual content. "
        f"The target is {word_limit} words — do not stop early. "
        f"Each body H2 section must contain at least {per_section} words; "
        "if a section feels thin, expand it with concrete examples, supporting evidence, or practical detail."
    )
    polish = (
        f"Keep textual content at or above {floor} words (target {word_limit}). "
        "Do not shorten or compress existing paragraphs — if any section is thin, expand it with concrete detail."
    )
    return draft, polish


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
    normalized_mode_type = _normalize_mode_type(mode_type)
    limits = _body_structure_limits(word_limit)
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
              ]
            }}

            Requirements:
            - All output must be written in {language}
            - Follow SEO blog rules:
              1. Meta title should stay within 60 characters
              2. Meta description should stay within 160 characters
              3. Use exactly one H1
              4. Structure should be H1, introduction, H2/H3 body, conclusion, FAQ
              5. FAQ should contain {limits["faq_count"]} natural follow-up questions for this target length
              6. Titles should reflect the core topic naturally
            - Outline should target approximately {word_limit} words/characters of textual content
            - For this target length, use at most {limits["max_h2"]} body H2 sections and at most {limits["max_h3"]} body H3 subsections in total
            - Only use H3 when it materially improves clarity; do not add H3 by default
            - Each body H2 section should carry enough substance for at least two meaningful paragraphs or one paragraph plus one list block
            - Headings should be specific, benefit-driven, and not generic
            - Link opportunities should describe relevant anchor ideas and use provided URLs only when available
            - Internal link plan should call out the best early-link placement when rule context requires it
            - Compliance notes should reflect disclaimers, compatibility notes, or banned-term constraints
            - Image briefs should describe helpful supporting visuals and mention topic placement advice
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
          "compliance_notes": ["", ""],
          "schema_suggestions": ["Article"],
          "trust_signals": ["author byline", "publish date", "last updated", "references"]
        }}

        Requirements:
        - All output must be written in {language}
        - Titles, section headings, anchor text, and body content must all use {language}
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
          2. an opening paragraph starting with bold "Quick Answer:" (inline, not a separate H2 heading), followed by 1-2 short paragraphs
          3. one or more body H2 sections with optional H3 subsections
          4. one H2 named References and Evidence to Verify
          5. one H2 named FAQ
          6. one H2 named Conclusion
        - The outline field must describe body sections only
        - For this target length, use at most {limits["max_h2"]} body H2 sections and at most {limits["max_h3"]} body H3 subsections in total
        - Only use H3 when it materially improves clarity; do not add H3 by default
        - Each body H2 section should carry enough substance for at least two meaningful paragraphs or one paragraph plus one list block
        - FAQ questions must be practical, natural, and closely related to the keyword and the questions readers would ask in daily decision-making
        - FAQ should contain {limits["faq_count"]} natural user questions for this target length
        - Do not plan or mention TL;DR, update log, appendix, or extra top-level sections outside the fixed structure
        - Headings should mirror user questions and retrieval intents
        - Do not invent external sources; describe the type of evidence needed
        - If AI Q&A reference answer or adopted source links are provided in rule context, use them as GEO research input and cite/link only the provided source URLs when appropriate
        - Meta title should stay within 60 characters
        - Meta description should stay within 160 characters
        - If internal links are required, plan them near the top of the article
        - Avoid third-party narrator phrasing such as "According to official docs" or "through official documentation we can conclude"
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
    normalized_mode_type = _normalize_mode_type(mode_type)
    limits = _body_structure_limits(word_limit)
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

            Requirements:
            - Return pure HTML only
            - Use h1, h2, h3, p, ul, li, strong, a tags only
            - Structure:
              1. exact H1
              2. introduction that answers intent quickly
              3. H2/H3 body sections
              4. conclusion
              5. FAQ section with {limits["faq_count"]} natural follow-up questions
            - {draft_word_instruction}
            - For this target length, use at most {limits["max_h2"]} body H2 sections and at most {limits["max_h3"]} body H3 subsections in total
            - Only use H3 when it materially improves clarity; do not add H3 by default
            - Each body H2 section should contain at least two meaningful content blocks, usually two paragraphs or one paragraph plus one list
            - When mode_type=1, keep the main keyword naturally present in H1, intro, and conclusion
            - Paragraphs should stay compact and readable
            - When mode_type=1, use long-tail keywords naturally and never stuff them
            - If brand/product info is provided, integrate it naturally without turning the article into a sales page
            - Use provided internal URLs when the strategy includes them; otherwise do not invent URLs
            - Respect all compliance notes, disclaimers, and compatibility constraints from the rule context
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

        Requirements:
        - Return pure HTML only
        - Use h1, h2, h3, p, ul, li, strong, a tags only
        - All visible text, including the H1 title, all headings, paragraph text, list text, and anchor text, must be written in {language}
        - The final structure must be exactly:
          1. one H1 title
          2. Quick Answer as inline bold text at the start of the opening paragraph (not a separate heading),followed by 1-2 short paragraphs
          3. one or more body H2 sections with optional H3 subsections
          4. one H2 with the exact text References and Evidence to Verify
          5. one H2 with the exact text FAQ
          6. one H2 with the exact text Conclusion
        - References and Evidence to Verify must appear immediately before FAQ
        - FAQ must appear immediately before Conclusion
        - For this target length, use at most {limits["max_h2"]} body H2 sections and at most {limits["max_h3"]} body H3 subsections in total
        - Only use H3 when it materially improves clarity; do not add H3 by default
        - Each body H2 section should contain at least two meaningful content blocks, usually two paragraphs or one paragraph plus one list
        - FAQ must contain {limits["faq_count"]} H3 questions, and each question must be a realistic user question related to {keyword}
        - Each FAQ question must be followed by one concise answer paragraph
        - Conclusion must be the final H2 section
        - Do not add TL;DR, update log, appendix, or any extra top-level section outside the fixed structure
        - {draft_word_instruction}
        - Use short, extractable paragraphs
        - Make headings easy for AI systems to quote or summarize
        - Mention citations, proof, benchmark data, or source types without inventing fake source URLs
        - Use AI Q&A reference answer and adopted source links from rule context as GEO reference material when provided
        - If brand/product info is provided, keep entity mentions consistent and verifiable
        - Use direct explanatory voice. Do not write in a third-party narrator tone such as "According to official docs", "Based on official documentation", or "through official documentation we can conclude"
        - Respect all compliance notes, disclaimers, and compatibility constraints from the rule context
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
    geo_requirements = (
        """
        - For GEO articles, the final structure must be exactly:
          1. one H1 title
          2. an opening paragraph starting with bold "Quick Answer:" (inline, not a separate H2 heading), followed by 1-2 short paragraphs
          3. one or more body H2 sections with optional H3 subsections
          4. one H2 named References and Evidence to Verify
          5. one H2 named FAQ
          6. one H2 named Conclusion as the final section
        - FAQ must stay immediately before Conclusion and contain 2-4 natural user questions related to the target keyword
        - Keep all headings and visible text in the requested language
        - Unless the article has a clear structural problem, do not add, remove, reorder, or rename sections
        - Default to polishing wording, headings, clarity, and fluency rather than restructuring
        - Remove AI-sounding phrasing, generic filler, and robotic repetition so the article reads like it was written by a human writer
        - Remove third-party narrator phrasing such as "According to official docs", "Based on official documentation", "through official documentation we can conclude", or "通过官方文档可以得出"
        - State conclusions directly, then place source guidance in the references section
        """
        if category == "geo"
        else ""
    )
    density_notes = _body_structure_limits(word_limit)
    _draft_word_instruction, polish_word_instruction = _word_count_instructions(word_limit, density_notes)
    return dedent(
        f"""
        You are an expert editor.
        Rewrite the HTML article below to sound more human and more useful.

        Goals:
        - {flavor}
        - {structure_requirement.removeprefix("- ")}
        - Do not change the core meaning
        - Keep the article in {language}
        - {topic_requirement}
        - {polish_word_instruction}
        - For this target length, keep the body within {density_notes["max_h2"]} H2 sections and {density_notes["max_h3"]} H3 subsections total whenever possible
        - If the draft already fits the structure, avoid adding new headings; strengthen the existing wording instead
        - Keep compliance with the following rule context:
        {rule_brief}
        {geo_requirements}
        {mode_requirement}
        - Return HTML only

        Article:
        {html}
        """
    ).strip()
