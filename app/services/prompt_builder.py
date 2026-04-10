from __future__ import annotations

from textwrap import dedent


def build_strategy_prompt(category: str, keyword: str, info: str, language: str) -> str:
    if category == "seo":
        return dedent(
            f"""
            You are a senior SEO content strategist.
            Create a writing strategy for the keyword "{keyword}".

            Brand or product information:
            {info or "None provided."}

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
              "link_opportunities": ["", ""]
            }}

            Requirements:
            - All output must be written in {language}
            - Follow SEO blog rules:
              1. Meta title should stay within 60 characters
              2. Meta description should stay within 160 characters
              3. Use exactly one H1
              4. Structure should be H1, introduction, H2/H3 body, conclusion, FAQ
              5. FAQ should contain 2-4 questions
              6. Titles must naturally include the main keyword
            - Outline should target a 1000-1500 word article
            - Headings should be specific, benefit-driven, and not generic
            - Link opportunities should describe relevant anchor ideas, not fake URLs
            - Image briefs should describe helpful supporting visuals and mention keyword placement advice
            """
        ).strip()

    return dedent(
        f"""
        You are a GEO content strategist focused on AI citability and answer extraction.
        Create a writing strategy for the keyword "{keyword}".

        Brand or product information:
        {info or "None provided."}

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
          6. clear entity alignment between keyword and brand/product info
          7. TL;DR and update-log friendly structure
        - Headings should mirror user questions and retrieval intents
        - Do not invent external sources; describe the type of evidence needed
        - Meta title should stay within 60 characters
        - Meta description should stay within 160 characters
        """
    ).strip()


def build_draft_prompt(
    category: str,
    keyword: str,
    info: str,
    language: str,
    strategy: dict,
    word_limit: int = 1200,
) -> str:
    if category == "seo":
        return dedent(
            f"""
            You are a senior SEO article writer.
            Use the strategy below to write a complete HTML article.

            Keyword: {keyword}
            Language: {language}
            Brand/Product info: {info or "None provided."}
            Strategy JSON:
            {strategy}

            Requirements:
            - Return pure HTML only
            - Use h1, h2, h3, p, ul, li, strong tags only
            - Structure:
              1. exact H1
              2. introduction that answers intent quickly
              3. H2/H3 body sections
              4. conclusion
              5. FAQ section with 2-4 questions
            - Target approximately {word_limit} words/characters of textual content (excluding any image content)
            - Main keyword must appear naturally in H1, intro, and conclusion
            - Paragraphs should stay compact and readable
            - Use long-tail keywords naturally, never stuff them
            - If brand/product info is provided, integrate it naturally without turning the article into a sales page
            - Do not invent URLs
            """
        ).strip()

    return dedent(
        f"""
        You are a GEO article writer focused on AI-ready answer extraction.
        Use the strategy below to write a complete HTML article.

        Keyword: {keyword}
        Language: {language}
        Brand/Product info: {info or "None provided."}
        Strategy JSON:
        {strategy}

        Requirements:
        - Return pure HTML only
        - Use h1, h2, h3, p, ul, li, strong tags only
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
        - If brand/product info is provided, keep entity mentions consistent and verifiable
        """
    ).strip()


def build_polish_prompt(category: str, language: str, keyword: str, html: str, word_limit: int = 1200) -> str:
    flavor = (
        "Improve naturalness, specificity, and SEO readability."
        if category == "seo"
        else "Improve citability, answer extraction, and trust signals."
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
        - Keep the keyword "{keyword}" naturally present
        - Keep textual content close to {word_limit} words/characters (excluding image content)
        - Return HTML only

        Article:
        {html}
        """
    ).strip()
