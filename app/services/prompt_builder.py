from __future__ import annotations

from textwrap import dedent
from typing import Any


MODE_TYPE_KEYWORD = 1
MODE_TYPE_OUTLINE = 2


def _normalize_mode_type(mode_type: int) -> int:
    return MODE_TYPE_OUTLINE if int(mode_type) == MODE_TYPE_OUTLINE else MODE_TYPE_KEYWORD


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
    mode_type: int = MODE_TYPE_KEYWORD,
) -> str:
    rule_brief = _build_rule_brief(rule_context or {})
    normalized_mode_type = _normalize_mode_type(mode_type)
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
              5. FAQ should contain 2-4 questions
              6. Titles should reflect the core topic naturally
            - Outline should target a 1000-1500 word article
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
          "schema_suggestions": ["Article", "FAQPage"],
          "trust_signals": ["author byline", "publish date", "last updated", "references", "TL;DR"]
        }}

        Requirements:
        - All output must be written in {language}
        - Optimize for GEO / AI citation readiness:
          1. answer-first structure
          2. high information density
          3. FAQ and extractable headings
          4. references and inline citation opportunities
          5. quantified proof blocks
          6. clear entity alignment between the topic and brand/product info
          7. TL;DR and update-log friendly structure
        - Headings should mirror user questions and retrieval intents
        - Do not invent external sources; describe the type of evidence needed
        - If AI Q&A reference answer or adopted source links are provided in rule context, use them as GEO research input and cite/link only the provided source URLs when appropriate
        - Meta title should stay within 60 characters
        - Meta description should stay within 160 characters
        - If internal links are required, plan them near the top of the article
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
              5. FAQ section with 2-4 questions
            - Target approximately {word_limit} words/characters of textual content (excluding any image content)
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
        - Structure should prioritize:
          1. H1
          2. TL;DR / answer-first intro
          3. clear proof-oriented H2/H3 blocks
          4. references / evidence guidance
          5. conclusion
          6. FAQ
        - Target approximately {word_limit} words/characters of textual content (excluding any image content)
        - Use short, extractable paragraphs
        - Make headings easy for AI systems to quote or summarize
        - Mention citations, proof, benchmark data, or source types without inventing fake source URLs
        - Use AI Q&A reference answer and adopted source links from rule context as GEO reference material when provided
        - If brand/product info is provided, keep entity mentions consistent and verifiable
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
        else "Improve citability, answer extraction, and trust signals."
    )
    rule_brief = _build_rule_brief(rule_context or {})
    normalized_mode_type = _normalize_mode_type(mode_type)
    topic_requirement = (
        'Keep the keyword "{keyword}" naturally present'.format(keyword=keyword)
        if normalized_mode_type == MODE_TYPE_KEYWORD
        else "Keep the article aligned to the supplied outline and preserve the heading wording intent"
    )
    mode_requirement = (
        "- mode_type=2: keep the exact heading structure, order, and section boundaries from the current HTML"
        if normalized_mode_type == MODE_TYPE_OUTLINE
        else ""
    )
    return dedent(
        f"""
        You are an expert editor.
        Rewrite the HTML article below to sound more human and more useful.

        Goals:
        - {flavor}
        - Keep the existing HTML structure intact
        - Do not change the core meaning
        - Keep the article in {language}
        - {topic_requirement}
        - Keep textual content close to {word_limit} words/characters (excluding image content)
        - Keep compliance with the following rule context:
        {rule_brief}
        {mode_requirement}
        - Return HTML only

        Article:
        {html}
        """
    ).strip()
