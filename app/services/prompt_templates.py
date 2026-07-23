"""Editable prompt templates.

Every prompt sent to the LLM is defined here as a default template. The admin
console persists overrides in a JSON file (see ``PromptStore``) so wording can be
changed at runtime without touching the code.

Placeholders use the ``{{name}}`` syntax so JSON braces inside a prompt stay
readable for editors.
"""

from __future__ import annotations

from dataclasses import dataclass


GROUP_STRATEGY = "文章策略"
GROUP_DRAFT = "文章初稿"
GROUP_POLISH = "文章润色"
GROUP_OUTLINE = "大纲生成"
GROUP_SHARED = "通用片段"


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    key: str
    group: str
    name: str
    description: str
    variables: tuple[str, ...]
    default: str


TEMPLATES: tuple[PromptTemplate, ...] = (
    PromptTemplate(
        key="strategy.seo",
        group=GROUP_STRATEGY,
        name="SEO 策略提示词",
        description="SEO 文章第一步：生成写作策略 JSON。",
        variables=(
            "competitor_policy",
            "mode_context",
            "rule_brief",
            "ai_answer_guidance",
            "cta_guidance",
            "v3_guidance",
            "language",
            "strict_language_line",
            "faq_count",
            "word_limit",
            "max_h2",
            "max_h3",
            "mode_requirements",
        ),
        default="""You are a senior SEO content strategist.
Create a writing strategy for the requested article.

{{mode_context}}

Rule context:
{{rule_brief}}

{{ai_answer_guidance}}

{{cta_guidance}}

{{v3_guidance}}

Return strict JSON only:
{
  "intent": "",
  "audience": "",
  "meta_title": "",
  "meta_description": "",
  "h1_options": ["", "", ""],
  "outline": [
    {"level": "H2", "title": ""},
    {"level": "H3", "title": ""}
  ],
  "longtail_keywords": ["", "", "", ""],
  "faq_questions": ["", "", ""],
  "image_briefs": ["", ""],
  "link_opportunities": ["", ""],
  "compliance_notes": ["", ""],
  "internal_link_plan": [
    {"label": "", "placement": "", "url_hint": ""}
  ],
  "cta_plan": {
    "reader_scenario": "",
    "next_action": "",
    "value": "",
    "conclusion_angle": ""
  }
}

Requirements:
- All output must be written in {{language}}
{{strict_language_line}}
- Follow SEO blog rules:
  1. Meta title should stay within 60 characters
  2. Meta description should stay within 160 characters
  3. Use exactly one H1
  4. Structure should be H1, introduction, H2/H3 body, conclusion, FAQ
  5. FAQ should contain {{faq_count}} natural follow-up questions for this target length
  6. When brand/product info is provided, include one FAQ question that captures product or solution fit, such as when the named option is a logical choice and when extra checking is needed
  7. Titles should reflect the core topic naturally
- Outline should target approximately {{word_limit}} words/characters of textual content
- HARD LIMIT: the outline must contain no more than {{max_h2}} body H2 sections — combine related subtopics into fewer sections rather than adding more H2s
- HARD LIMIT: use no more than {{max_h3}} body H3 subsections in total
- In plain terms: use at most {{max_h2}} body H2 sections and at most {{max_h3}} body H3 subsections
- Only use H3 when it materially improves clarity; do not add H3 by default
- Each body H2 section should be concise — plan for one to two short paragraphs per section, not multi-paragraph deep dives
- Headings should be specific, benefit-driven, and not generic
- Link opportunities should describe relevant anchor ideas and use provided URLs only when available
- Internal link plan should call out the best early-link placement when rule context requires it
- Build cta_plan around the reader's scenario, the next action they should take, and the value they gain from that action
- If a product or solution is a candidate recommendation, plan one sentence explaining why it is worth comparing in this scenario, especially when staged adoption, limited budget, uncertain incentives, or later expansion affects the decision
- Compliance notes should reflect disclaimers, compatibility notes, or banned-term constraints
- Image briefs should describe helpful supporting visuals and mention topic placement advice
- {{competitor_policy}}
{{mode_requirements}}""",
    ),
    PromptTemplate(
        key="strategy.geo",
        group=GROUP_STRATEGY,
        name="GEO 策略提示词",
        description="GEO 文章第一步：生成面向 AI 引用的写作策略 JSON。",
        variables=(
            "competitor_policy",
            "mode_context",
            "rule_brief",
            "ai_answer_guidance",
            "cta_guidance",
            "v3_guidance",
            "language",
            "strict_language_line",
            "quick_answer_prefix",
            "references_heading",
            "faq_heading",
            "conclusion_heading",
            "faq_count",
            "max_h2",
            "max_h3",
            "mode_requirements",
        ),
        default="""You are a GEO content strategist focused on AI citability and answer extraction.
Create a writing strategy for the requested article.

{{mode_context}}

Rule context:
{{rule_brief}}

{{ai_answer_guidance}}

{{cta_guidance}}

{{v3_guidance}}

Return strict JSON only:
{
  "search_intent": "",
  "audience": "",
  "meta_title": "",
  "meta_description": "",
  "answer_first_summary": "",
  "entity_summary": "",
  "h1_options": ["", "", ""],
  "outline": [
    {"level": "H2", "title": ""},
    {"level": "H3", "title": ""}
  ],
  "claim_blocks": [
    {"claim": "", "proof_hint": "", "citation_hint": ""}
  ],
  "faq_questions": ["", "", ""],
  "reference_plan": ["", ""],
  "internal_link_plan": [
    {"label": "", "placement": "", "url_hint": ""}
  ],
  "cta_plan": {
    "reader_scenario": "",
    "next_action": "",
    "value": "",
    "conclusion_angle": ""
  },
  "compliance_notes": ["", ""],
  "schema_suggestions": ["Article"],
  "trust_signals": ["author byline", "publish date", "last updated", "references"]
}

Requirements:
- All output must be written in {{language}}
- Titles, section headings, anchor text, and body content must all use {{language}}
{{strict_language_line}}
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
  2. an opening paragraph starting with bold "{{quick_answer_prefix}}:" (inline, not a separate H2 heading), followed by 1-2 short paragraphs
  3. one or more body H2 sections with optional H3 subsections
  4. one H2 named {{references_heading}}
  5. one H2 named {{faq_heading}}
  6. one H2 named {{conclusion_heading}}
- The outline field must describe body sections only
- Do not add a short-answer heading (such as "{{quick_answer_prefix}}", "Quick Answer", "Quick Verdict", "TL;DR", or "简而言之") to the outline; the quick answer belongs in the inline opening paragraph, not as an H2/H3 section
- In plain terms: use at most {{max_h2}} body H2 sections and at most {{max_h3}} body H3 subsections
- HARD LIMIT: the outline must contain no more than {{max_h2}} body H2 sections — combine related subtopics into fewer sections rather than adding more H2s
- HARD LIMIT: use no more than {{max_h3}} body H3 subsections in total
- Only use H3 when it materially improves clarity; do not add H3 by default
- Each body H2 section should be concise — plan for one to two short paragraphs per section, not multi-paragraph deep dives
- FAQ questions must be practical, natural, and closely related to the keyword and the questions readers would ask in daily decision-making
- FAQ should contain {{faq_count}} natural user questions for this target length
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
- {{competitor_policy}}
- For the reference_plan field, list authoritative local organizations relevant to the country/market context (e.g., government agencies, national standards institutes, industry regulators, official academic institutions). Each entry should follow the format: "<Organization Name> — <Document or Publication Title> — <URL>". Do not use generic placeholder descriptions.
{{mode_requirements}}""",
    ),
    PromptTemplate(
        key="draft.seo",
        group=GROUP_DRAFT,
        name="SEO 初稿提示词",
        description="SEO 文章第二步：根据策略写出 HTML 初稿。",
        variables=(
            "language",
            "mode_context",
            "strategy_json",
            "rule_brief",
            "ai_answer_guidance",
            "cta_guidance",
            "v3_guidance",
            "strict_language_line",
            "faq_count",
            "word_count_instruction",
            "max_h2",
            "max_h3",
            "mode_requirements",
        ),
        default="""You are a senior SEO article writer.
Use the strategy below to write a complete HTML article.

Language: {{language}}
{{mode_context}}
Strategy JSON:
{{strategy_json}}
Rule context:
{{rule_brief}}

{{ai_answer_guidance}}

{{cta_guidance}}

{{v3_guidance}}

Requirements:
- Return pure HTML only
- Use h1, h2, h3, p, ul, li, strong, a tags only
- All visible text must be written in {{language}}
{{strict_language_line}}
- Structure:
  1. exact H1
  2. introduction that answers intent quickly
  3. H2/H3 body sections
  4. conclusion
  5. FAQ section with {{faq_count}} natural follow-up questions
- {{word_count_instruction}}
- HARD LIMIT: use exactly {{max_h2}} body H2 sections maximum — do not add more H2 sections even if the topic seems to warrant it
- HARD LIMIT: use at most {{max_h3}} H3 subsections total across the entire article
- In plain terms: use at most {{max_h2}} body H2 sections and at most {{max_h3}} body H3 subsections
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
{{mode_requirements}}""",
    ),
    PromptTemplate(
        key="draft.geo",
        group=GROUP_DRAFT,
        name="GEO 初稿提示词",
        description="GEO 文章第二步：按固定结构写出可被 AI 引用的 HTML 初稿。",
        variables=(
            "competitor_policy",
            "language",
            "mode_context",
            "strategy_json",
            "rule_brief",
            "ai_answer_guidance",
            "cta_guidance",
            "v3_guidance",
            "strict_language_line",
            "keyword",
            "quick_answer_prefix",
            "references_heading",
            "faq_heading",
            "conclusion_heading",
            "faq_count",
            "word_count_instruction",
            "max_h2",
            "max_h3",
            "mode_requirements",
        ),
        default="""You are a GEO article writer focused on AI-ready answer extraction.
Use the strategy below to write a complete HTML article.

Language: {{language}}
{{mode_context}}
Strategy JSON:
{{strategy_json}}
Rule context:
{{rule_brief}}

{{ai_answer_guidance}}

{{cta_guidance}}

{{v3_guidance}}

Requirements:
- Return pure HTML only
- Use h1, h2, h3, p, ul, li, strong, a tags only
- All visible text, including the H1 title, all headings, paragraph text, list text, and anchor text, must be written in {{language}}
{{strict_language_line}}
- The final structure must be exactly:
  1. one H1 title
  2. {{quick_answer_prefix}} as inline bold text at the start of the opening paragraph (not a separate heading), followed by 1-2 short paragraphs
  3. one or more body H2 sections with optional H3 subsections
  4. one H2 with the exact text {{references_heading}}
  5. one H2 with the exact text {{faq_heading}}
  6. one H2 with the exact text {{conclusion_heading}}
- {{references_heading}} must appear immediately before {{faq_heading}}
- {{faq_heading}} must appear immediately before {{conclusion_heading}}
- HARD LIMIT: use exactly {{max_h2}} body H2 sections maximum — do not add extra H2 sections beyond this count
- HARD LIMIT: use at most {{max_h3}} H3 subsections total across the entire article
- In plain terms: use at most {{max_h2}} body H2 sections and at most {{max_h3}} body H3 subsections
- Only use H3 when it materially improves clarity; do not add H3 by default
- Each body H2 section should contain at most two short paragraphs; avoid long multi-paragraph sections
- {{faq_heading}} must contain {{faq_count}} H3 questions, and each question must be a realistic user question related to {{keyword}}
- When brand/product info is provided, one FAQ question must ask when the named product, model, or solution is a logical option; answer with suitable scenarios, unsuitable scenarios, and what to verify first
- Each FAQ question must be followed by one concise answer paragraph
- {{conclusion_heading}} must be the final H2 section
- Do not add TL;DR, update log, appendix, or any extra top-level section outside the fixed structure
- If the provided outline contains an early short-answer heading (for example "{{quick_answer_prefix}}", "Quick Answer", "Quick Verdict", "TL;DR", or "简而言之"), do NOT keep it as an H2 or H3; fold its content into the inline bold "{{quick_answer_prefix}}:" opening paragraph instead. This is the one intended exception to preserving the outline headings.
- {{word_count_instruction}}
- Use short, extractable paragraphs
- Make headings easy for AI systems to quote or summarize
- For the References and Evidence to Verify section, cite real authoritative local organizations relevant to the country/market (e.g., government agencies, national standards institutes, industry regulators, official academic institutions). Each reference entry must include the organization name, document or publication title, and a real URL. Do not use placeholder text or invent sources.
- Use AI Q&A reference answer and adopted source links from rule context as GEO reference material when provided
- When AI Q&A data is present, explicitly separate answer, conditions, constraints, alternatives, recommendation tiers, and evidence limits
- If brand/product info is provided, keep entity mentions consistent and verifiable
- When presenting any product or solution as a candidate, explain why it is worth comparing for this reader's scenario before asking the reader to take the next step
- Use direct explanatory voice. Do not write in a third-party narrator tone such as "According to official docs", "Based on official documentation", or "through official documentation we can conclude"
- {{competitor_policy}}
- Respect all compliance notes, disclaimers, and compatibility constraints from the rule context
- Use strategy.cta_plan when present; the conclusion must summarize the core judgment and include one soft CTA tied to the reader's scenario, next action, and practical value
{{mode_requirements}}""",
    ),
    PromptTemplate(
        key="polish.main",
        group=GROUP_POLISH,
        name="润色提示词（主体）",
        description="第三步：重写初稿，使其更像人写并符合字数与结构限制。SEO / GEO 共用。",
        variables=(
            "flavor",
            "structure_requirement",
            "language",
            "strict_language_line",
            "topic_requirement",
            "word_count_instruction",
            "max_h2",
            "max_h3",
            "rule_brief",
            "ai_answer_guidance",
            "cta_guidance",
            "v3_guidance",
            "geo_requirements",
            "mode_requirement",
            "html",
        ),
        default="""You are an expert editor.
Rewrite the HTML article below to sound more human and more useful.

Goals:
- {{flavor}}
- {{structure_requirement}}
- Do not change the core meaning
- Keep the article in {{language}}
{{strict_language_line}}
- {{topic_requirement}}
- {{word_count_instruction}}
- HARD LIMIT: the article must have no more than {{max_h2}} body H2 sections and {{max_h3}} body H3 subsections — if the draft exceeds this, merge or remove the least essential sections
- For this target length, keep the body within {{max_h2}} H2 sections and {{max_h3}} H3 subsections total; avoid adding new headings
- Do not add new headings; shorten or merge existing sections to meet the word count limit
- If the article names a product, model, or first-party solution, ensure the copy explains why it is worth comparing for the user's scenario before the final CTA
- Make the final CTA action-specific by naming the comparison or verification dimensions the reader should check next
- Keep compliance with the following rule context:
{{rule_brief}}
- Apply this AI-answer-data guidance where relevant:
{{ai_answer_guidance}}
- Apply this CTA and conclusion guidance where relevant:
{{cta_guidance}}
{{v3_guidance}}
{{geo_requirements}}
{{mode_requirement}}
- Return HTML only

Article:
{{html}}""",
    ),
    PromptTemplate(
        key="polish.geo_requirements",
        group=GROUP_POLISH,
        name="润色附加要求（仅 GEO）",
        description="GEO 文章润色时追加的结构与语气要求。",
        variables=(
            "quick_answer_prefix",
            "references_heading",
            "faq_heading",
            "conclusion_heading",
            "faq_count",
            "strict_language_line",
        ),
        default="""- For GEO articles, the final structure must be exactly:
  1. one H1 title
  2. an opening paragraph starting with bold "{{quick_answer_prefix}}:" (inline, not a separate H2 heading), followed by 1-2 short paragraphs
  3. one or more body H2 sections with optional H3 subsections
  4. one H2 named {{references_heading}}
  5. one H2 named {{faq_heading}}
  6. one H2 named {{conclusion_heading}} as the final section
- If an early short-answer heading survived as an H2/H3 (for example "{{quick_answer_prefix}}", "Quick Answer", "Quick Verdict", "TL;DR", or "简而言之"), fold its content into the inline bold "{{quick_answer_prefix}}:" opening paragraph and remove that heading
- {{faq_heading}} must stay immediately before {{conclusion_heading}} and contain {{faq_count}} natural user questions related to the target keyword
- If a named product, model, or solution appears, keep or add one natural FAQ that explains when it is a logical option and when extra verification is needed, without adding a new top-level section
- Keep all headings and visible text in the requested language
{{strict_language_line}}
- Unless the article has a clear structural problem, do not add, remove, reorder, or rename sections
- Default to polishing wording, headings, clarity, and fluency rather than restructuring
- Remove AI-sounding phrasing, generic filler, and robotic repetition so the article reads like it was written by a human writer
- Remove third-party narrator phrasing such as "According to official docs", "Based on official documentation", "through official documentation we can conclude", or "通过官方文档可以得出"
- State conclusions directly, then place source guidance in the references section
- If the References and Evidence to Verify section contains placeholder text or invented sources, replace them with real authoritative local organizations (government agencies, national standards institutes, industry regulators, or official academic institutions), each with organization name, document/publication title, and a real URL
- If the keyword signals a comparison or alternatives intent, ensure the article does not name or recommend specific competing brands; replace any competitor mentions with neutral criteria-based comparisons""",
    ),
    PromptTemplate(
        key="polish.flavor.seo",
        group=GROUP_POLISH,
        name="润色目标 · SEO",
        description="SEO 润色的首要目标，单行。",
        variables=(),
        default="Improve naturalness, specificity, and SEO readability.",
    ),
    PromptTemplate(
        key="polish.flavor.geo",
        group=GROUP_POLISH,
        name="润色目标 · GEO",
        description="GEO 润色的首要目标，单行。",
        variables=(),
        default="Improve citability, answer extraction, trust signals, and structural consistency.",
    ),
    PromptTemplate(
        key="polish.structure.seo",
        group=GROUP_POLISH,
        name="润色结构约束 · SEO",
        description="SEO 润色时对原结构的处理方式，单行。",
        variables=(),
        default="Keep the existing HTML structure intact",
    ),
    PromptTemplate(
        key="polish.structure.geo",
        group=GROUP_POLISH,
        name="润色结构约束 · GEO",
        description="GEO 润色时对原结构的处理方式，单行。",
        variables=(),
        default="Keep the existing structure and section order unless there is an obvious structural problem that must be repaired",
    ),
    PromptTemplate(
        key="polish.topic.keyword",
        group=GROUP_POLISH,
        name="润色主题约束 · 关键词模式",
        description="mode_type=1 时的主题保持要求。",
        variables=("keyword",),
        default='Keep the keyword "{{keyword}}" naturally present',
    ),
    PromptTemplate(
        key="polish.topic.outline",
        group=GROUP_POLISH,
        name="润色主题约束 · 大纲模式",
        description="mode_type=2 时的主题保持要求。",
        variables=(),
        default="Keep the article aligned to the supplied outline and preserve the heading wording intent",
    ),
    PromptTemplate(
        key="outline.v2",
        group=GROUP_OUTLINE,
        name="大纲提示词 2.0",
        description="内容版本 2.0 的大纲生成提示词。",
        variables=(
            "mode_name",
            "keyword",
            "info_block",
            "language",
            "task_context_block",
            "link_lines",
            "ai_answer_guidance",
            "cta_guidance",
            "mode_requirements",
            "word_limit",
            "max_h2",
            "max_h3",
            "faq_count",
        ),
        default="""You are a senior {{mode_name}} content strategist.
Create a clean article outline plan for the keyword below.

Keyword:
{{keyword}}

Business context:
{{info_block}}

Language:
{{language}}

Task context:
{{task_context_block}}

Allowed internal links:
{{link_lines}}

AI-answer-data writing guidance:
{{ai_answer_guidance}}

{{cta_guidance}}

Requirements:
{{mode_requirements}}
- Target approximately {{word_limit}} words/characters of textual content in the final article.
- For this target length, keep the outline body within {{max_h2}} H2 sections and {{max_h3}} H3 subsections total.
- Only use H3 when it materially improves clarity; do not add H3 by default.
- FAQ should contain {{faq_count}} natural questions for this target length.
- Each body H2 should be substantial enough to support at least two meaningful content blocks in the final article.
- Keep the outline practical, specific, and commercially relevant without sounding like an ad.
- Use the business context and country rules when deciding comparison criteria and examples.
- If a product, model, or first-party solution is introduced as a candidate, plan a short reason explaining why it is worth comparing for this specific reader scenario, using practical factors such as staged adoption, lower upfront commitment, capacity fit, installation requirements, verified specifications, or future expandability when supported by the input.
- Use AI Q&A reference answer and adopted source links as GEO research input when provided.
- If AI Q&A data includes product recommendations or explore_more items, distinguish primary recommendations, secondary recommendations, exploratory related items, and internal search queries.
- Preserve evidence boundaries: do not infer search volume, conversion rate, official approval, or user behavior unless the input data explicitly provides it.
- Plan the conclusion so it restates the core judgment and ends with a soft CTA built from reader scenario + next action + practical value.
- For subsidy, local policy uncertainty, budget-sensitive, installation-fit, or product-selection topics, guide the reader to check actual capacity, expandability, installation requirements, and official specifications against their own usage habits, budget, and subsidy situation.
- Make the CTA action-specific by naming the comparison dimensions: usage, available subsidy, installation conditions, capacity, expandability, and official specifications where relevant.
- When brand/product info is provided, plan one FAQ question about when the named product, model, or solution is a logical option, and answer with fit conditions plus what needs extra verification.
- Keep CTAs professional and useful: no hard-sell pressure, exaggerated benefits, or anxiety-driven framing.
- Only recommend internal links from the allowed list above.
- If a Shopify URL is required, place it naturally in the early buying-intent section.
- If the keyword signals a comparison or alternatives intent (e.g., contains "vs", "versus", "alternatives", "best X for Y", "compare"), do not name or recommend specific competing brands or products anywhere in the outline or writing suggestions; base comparisons only on neutral criteria, use-case fit, and objective specifications.
- For any references or sources section in the outline, plan to cite real authoritative local organizations relevant to the country/market context (e.g., government agencies, national standards institutes, industry regulators, official academic institutions). Each planned reference should include the organization name, document or publication title, and a real URL. Do not use generic placeholder descriptions.
- Return an outline a writer can use immediately.

Return strict JSON only:
{
  "title": "",
  "outline_markdown": "",
  "writing_suggestions": ["", "", ""],
  "recommended_internal_links": [
    {
      "label": "",
      "url": "",
      "reason": ""
    }
  ]
}""",
    ),
    PromptTemplate(
        key="outline.mode.seo",
        group=GROUP_OUTLINE,
        name="大纲模式要求 · SEO",
        description="2.0 大纲提示词中 SEO 模式的专属要求。",
        variables=(),
        default="""- Optimize for search intent alignment, H1/H2/H3 structure, natural keyword coverage, readability, and internal linking.
- Make the outline directly usable for an SEO article.
- Include a strong intro, clear section hierarchy, conclusion, and FAQ.""",
    ),
    PromptTemplate(
        key="outline.mode.geo",
        group=GROUP_OUTLINE,
        name="大纲模式要求 · GEO",
        description="2.0 大纲提示词中 GEO 模式的专属要求。",
        variables=(),
        default="""- Optimize for answer-first extraction, AI readability, clear entities, FAQ, citations, and trust signals.
- Make the outline directly usable for a GEO article.
- The opening should answer the query quickly as inline introductory text; do NOT create a separate 'Quick Answer', 'TL;DR', 'Kort antwoord', or '简而言之' H2/H3 heading for it.
- Include sections for sources/verification and FAQ.""",
    ),
    PromptTemplate(
        key="outline.v3",
        group=GROUP_OUTLINE,
        name="大纲提示词 3.0",
        description="内容版本 3.0 的紧凑型大纲提示词。",
        variables=(
            "mode_name",
            "keyword",
            "info_block",
            "language",
            "publishing_note",
            "country",
            "market",
            "locale",
            "ai_qa_content",
            "ai_qa_source",
            "shopify_note",
            "link_lines",
            "ai_answer_guidance",
            "cta_guidance",
            "h2_min",
            "h2_max",
            "faq_count",
        ),
        default="""You are a senior {{mode_name}} content strategist.
Create a version 3.0 article outline.

Keyword:
{{keyword}}

Business context:
{{info_block}}

Language:
{{language}}

Publishing context:
{{publishing_note}}

Task context:
- Country: {{country}}
- Market: {{market}}
- Locale: {{locale}}
- AI Q&A reference answer: {{ai_qa_content}}
- AI Q&A adopted source links: {{ai_qa_source}}
- Shopify URL required: {{shopify_note}}

Allowed internal links:
{{link_lines}}

AI-answer-data writing guidance:
{{ai_answer_guidance}}

{{cta_guidance}}

Version 3.0 outline style:
- Keep the outline compact and high-signal. Do not create a detailed paragraph-by-paragraph writing plan.
- outline_markdown must be a short line-based skeleton only, not a full SEO brief.
- Use exactly this output shape inside outline_markdown:
  H1: ...
  H2: ... - coverage query: "..."
  H2: ... - decision factor: "..."
  FAQ ({{faq_count}} questions)
  Internal Links: ...
- Do not include URL, slug, SEO title, meta description, intro notes, section descriptions, Markdown heading syntax (# or ##), or bullets under each H2 inside outline_markdown.
- Plan {{h2_min}}-{{h2_max}} H2 lines only. Use no H3 sections unless the keyword explicitly requires grouped subtopics.
- Each H2 must be one line only and should include one concise intent note such as: coverage query, user question, comparison angle, proof source, review source, or decision factor.
- Put the quick answer / verdict in the inline opening lines under the H1, not as a separate "Quick Verdict", "TL;DR", "Kort antwoord", or "简而言之" H2. Start the body H2 lines with the first real content or coverage section.
- Include a side-by-side specs or criteria table section when the topic compares products, models, specs, or options.
- Include review/evidence summary sections only when sources are provided or named in the input; do not invent source names.
- FAQ should be listed as "FAQ ({{faq_count}} questions)" rather than writing every FAQ answer in the outline.
- Internal links should be listed by page type or provided URL label; use only allowed internal links when URLs are provided.
- If brand/product info is provided, include one H2 or FAQ angle that explains when the named product/model/solution is a logical option.
- Keep product recommendations scenario-bound. Do not call a product the universal best choice.
- Return an outline a writer can use immediately, but keep outline_markdown close to the compact example style rather than a detailed plan.

Return strict JSON only:
{
  "title": "",
  "outline_markdown": "",
  "writing_suggestions": ["", "", ""],
  "recommended_internal_links": [
    {
      "label": "",
      "url": "",
      "reason": ""
    }
  ]
}""",
    ),
    PromptTemplate(
        key="outline.publishing.official_website",
        group=GROUP_OUTLINE,
        name="3.0 大纲发布场景 · 官网",
        description="3.0 大纲中 official_website 场景说明。",
        variables=(),
        default=(
            "official_website: first-party brand article. Prioritize the provided brand/product when the input supports it. "
            "Avoid competitor recommendations unless the keyword explicitly requires comparison; compare competitors only "
            "through objective specs, criteria, and fit."
        ),
    ),
    PromptTemplate(
        key="outline.publishing.third_party_media",
        group=GROUP_OUTLINE,
        name="3.0 大纲发布场景 · 第三方媒体",
        description="3.0 大纲中 third_party_media 场景说明。",
        variables=(),
        default=(
            "third_party_media: neutral editorial article. Use balanced comparison, objective criteria, evidence, and clear "
            "pros/cons. Competitors or alternatives may be named when relevant."
        ),
    ),
    PromptTemplate(
        key="outline.publishing.conversion_page",
        group=GROUP_OUTLINE,
        name="3.0 大纲发布场景 · 转化页",
        description="3.0 大纲中 conversion_page 场景说明。",
        variables=(),
        default=(
            "conversion_page: buying-decision or landing-page content. Make the primary product, fit scenario, proof points, "
            "and CTA clearer, while avoiding exaggerated claims or pressure."
        ),
    ),
    PromptTemplate(
        key="shared.ai_answer_data.base",
        group=GROUP_SHARED,
        name="AI 问答数据指引（通用）",
        description="策略 / 初稿 / 润色 / 大纲都会带上的 AI 问答数据使用规则。",
        variables=(),
        default="""AI-answer-data writing guidance:
- If AI Q&A reference data is provided, treat it as research evidence about how AI systems framed the query, not as ground truth.
- Start from the user's real question and answer it directly before expanding into background.
- Prefer conditional conclusions when the data supports them, such as "yes, but only when..." or "it depends on...".
- Separate the target product/entity, use case, suitable scenarios, unsuitable scenarios, risks, and alternatives.
- When recommendations appear in AI Q&A data, distinguish between primary recommendations, secondary recommendations, and exploratory/related items.
- Do not confuse AI internal search queries with user-facing recommendation terms.
- Preserve evidence boundaries: say what the provided data supports, and avoid claiming search volume, conversion rate, official approval, or user behavior unless the input explicitly provides it.
- Use compact tables or bullet lists for scenario fit, constraints, recommendation tiers, and evidence gaps when they make the answer easier to scan.""",
    ),
    PromptTemplate(
        key="shared.ai_answer_data.seo",
        group=GROUP_SHARED,
        name="AI 问答数据指引 · SEO 补充",
        description="追加在通用 AI 问答指引之后。",
        variables=(),
        default=(
            "- For SEO, turn AI Q&A insights into practical content sections that match search intent: direct answer, "
            "decision criteria, fit matrix, alternatives, FAQ, and next-step internal links."
        ),
    ),
    PromptTemplate(
        key="shared.ai_answer_data.geo",
        group=GROUP_SHARED,
        name="AI 问答数据指引 · GEO 补充",
        description="追加在通用 AI 问答指引之后。",
        variables=(),
        default="""- For GEO, make the opening answer extractable, then explain the AI reasoning path: product/entity positioning, scenario split, constraints, alternatives, and verification points.
- Add a section or subsection that makes the "recommended for / not recommended for" distinction explicit when the topic involves compatibility or product fit.""",
    ),
    PromptTemplate(
        key="shared.cta.base",
        group=GROUP_SHARED,
        name="CTA 与结尾指引（通用）",
        description="所有提示词共用的 CTA 写法约束。",
        variables=(),
        default="""CTA and conclusion guidance:
- Any CTA must combine the user's scenario, the next action, and the practical value of taking that action.
- Avoid standalone "buy now" language, hard-sell pressure, exaggerated savings, or anxiety-driven framing.
- When a product, model, or first-party solution is introduced as a candidate, explain why it is worth comparing for the reader's scenario instead of only naming it. Tie the reason to practical decision factors such as lower upfront commitment, staged expansion, capacity fit, installation simplicity, verified specifications, or future flexibility when the input supports those claims.
- For topics involving limited subsidies, uncertain local policy, budget sensitivity, installation fit, or product selection, guide readers to compare their own usage, available subsidy, installation conditions, actual capacity, expandability, and official specifications before judging fit.
- The conclusion must restate the core judgment, then add a soft next step such as comparing product fit, checking official specifications, confirming installation conditions, or reviewing an official product page when a provided URL is available.
- Make the final CTA action-specific: tell the reader what to compare or verify next, not only that they should "learn more" or "consider the product".
- Keep the tone professional, credible, and practical.""",
    ),
    PromptTemplate(
        key="shared.cta.seo",
        group=GROUP_SHARED,
        name="CTA 指引 · SEO 补充",
        description="追加在通用 CTA 指引之后。",
        variables=(),
        default=(
            "- For SEO, use the CTA to support search intent and internal linking without interrupting the article's "
            "direct answer."
        ),
    ),
    PromptTemplate(
        key="shared.cta.geo",
        group=GROUP_SHARED,
        name="CTA 指引 · GEO 补充",
        description="追加在通用 CTA 指引之后。",
        variables=(),
        default=(
            "- For GEO, make the final next step easy to extract as practical guidance, not as a conversion-heavy sales pitch."
        ),
    ),
    PromptTemplate(
        key="shared.strict_language",
        group=GROUP_SHARED,
        name="语言纯度警告",
        description="目标语言不是英语时追加的语言约束。",
        variables=("language",),
        default=(
            "STRICT LANGUAGE RULE: Every single word in the entire article — including the H1 title, every H2 and H3 "
            "heading, the Quick Answer prefix, all paragraph text, all list items, and all anchor text — must be written "
            "exclusively in {{language}}. Do NOT use English words, phrases, or abbreviations anywhere, not even for "
            "section headings or labels. Translate every fixed section name into {{language}} as instructed. Writing even "
            "one English word in a {{language}} article is a critical error."
        ),
    ),
    PromptTemplate(
        key="shared.language_mix_fallback",
        group=GROUP_SHARED,
        name="语言混用兜底（英文文章）",
        description="目标语言为英语时，GEO 润色使用的替代句。",
        variables=(),
        default="Do not mix languages within the article.",
    ),
    PromptTemplate(
        key="shared.word_count.draft",
        group=GROUP_SHARED,
        name="字数控制 · 初稿",
        description="初稿阶段的字数要求，数值由目标字数自动计算。",
        variables=("word_limit", "floor", "ceiling", "per_section", "per_section_max"),
        default=(
            "Target length: approximately {{word_limit}} words excluding any image content. The entire article — every "
            "section combined including intro, all H2/H3 body sections, FAQ, references, and conclusion — must total "
            "between {{floor}} and {{ceiling}} words. Each individual section should aim for around {{per_section}} words; "
            "do not write more than {{per_section_max}} words per section. Stop adding content once the running total "
            "approaches {{ceiling}} words."
        ),
    ),
    PromptTemplate(
        key="shared.word_count.polish",
        group=GROUP_SHARED,
        name="字数控制 · 润色",
        description="润色阶段的字数要求，数值由目标字数自动计算。",
        variables=("word_limit", "floor", "ceiling"),
        default=(
            "Target length: approximately {{word_limit}} words excluding image content. The entire article must total "
            "between {{floor}} and {{ceiling}} words. Count ALL sections: intro, body H2s, H3s, FAQ, references, and "
            "conclusion. If the total exceeds {{ceiling}} words, shorten the longest sections first. Do not expand any "
            "section unless the total is clearly under {{floor}} words."
        ),
    ),
    PromptTemplate(
        key="shared.v3.guidance",
        group=GROUP_SHARED,
        name="3.0 发布场景指引",
        description="内容版本 3.0 时追加到策略 / 初稿 / 润色的说明。",
        variables=("publishing_note",),
        default="""Content version: 3.0.
{{publishing_note}}
For version 3.0, make product recommendations scenario-bound: name the candidate product when provided, explain why it should be compared early for the reader's use case, and keep the limits/verification points explicit.""",
    ),
    PromptTemplate(
        key="shared.v3.official_website",
        group=GROUP_SHARED,
        name="3.0 场景说明 · 官网",
        description="content_version=3.0 且发布场景为官网时的语气说明。",
        variables=(),
        default=(
            "Publishing context: official_website. Use a first-party brand voice. The article may prioritize the brand's "
            "own product or model when the input supports it. Avoid naming competing products unless the keyword "
            "explicitly requires a comparison; when comparison is required, compare on objective criteria and do not "
            "endorse competitors."
        ),
    ),
    PromptTemplate(
        key="shared.v3.third_party_media",
        group=GROUP_SHARED,
        name="3.0 场景说明 · 第三方媒体",
        description="content_version=3.0 且发布场景为第三方媒体时的语气说明。",
        variables=(),
        default=(
            "Publishing context: third_party_media. Use a neutral editorial voice. Product recommendations must be "
            "balanced with clear criteria, trade-offs, and evidence. Competing brands or alternatives may be discussed "
            "when relevant to the search intent."
        ),
    ),
    PromptTemplate(
        key="shared.v3.conversion_page",
        group=GROUP_SHARED,
        name="3.0 场景说明 · 转化页",
        description="content_version=3.0 且发布场景为转化页时的语气说明。",
        variables=(),
        default=(
            "Publishing context: conversion_page. Use a practical buying-decision voice. Make the product fit, scenario "
            "fit, proof points, and next action clearer than in a neutral article. CTA can be stronger, but must stay "
            "evidence-based and avoid exaggerated claims or pressure."
        ),
    ),
    PromptTemplate(
        key="shared.context.strategy.keyword",
        group=GROUP_SHARED,
        name="输入块 · 策略（关键词模式）",
        description="mode_type=1 时策略提示词中的输入区块。",
        variables=("keyword", "info"),
        default="""Keyword:
{{keyword}}

Brand or product information:
{{info}}""",
    ),
    PromptTemplate(
        key="shared.context.strategy.outline",
        group=GROUP_SHARED,
        name="输入块 · 策略（大纲模式）",
        description="mode_type=2 时策略提示词中的输入区块。",
        variables=("keyword", "info"),
        default="""Provided outline from the keyword field:
{{keyword}}

Brand or product information:
{{info}}""",
    ),
    PromptTemplate(
        key="shared.context.draft.keyword",
        group=GROUP_SHARED,
        name="输入块 · 初稿（关键词模式）",
        description="mode_type=1 时初稿提示词中的输入区块。",
        variables=("keyword", "info"),
        default="""Keyword: {{keyword}}
Brand/Product info: {{info}}""",
    ),
    PromptTemplate(
        key="shared.context.draft.outline",
        group=GROUP_SHARED,
        name="输入块 · 初稿（大纲模式）",
        description="mode_type=2 时初稿提示词中的输入区块。",
        variables=("keyword", "info"),
        default="""Outline from keyword field:
{{keyword}}
Brand/Product info: {{info}}""",
    ),
    PromptTemplate(
        key="shared.mode2.strategy",
        group=GROUP_SHARED,
        name="大纲模式附加要求 · 策略",
        description="mode_type=2 时追加到策略提示词末尾。",
        variables=(),
        default="""- mode_type=2 means the keyword field contains the required outline, not a short SEO keyword
- Preserve the outline hierarchy, heading order, and section intent from the keyword field
- Do not invent extra H2/H3 sections unless a minimal structural repair is required
- If the outline contains an H1, use it as the primary H1 option
- Use the brand/product info only as supporting context inside the provided outline""",
    ),
    PromptTemplate(
        key="shared.mode2.draft",
        group=GROUP_SHARED,
        name="大纲模式附加要求 · 初稿",
        description="mode_type=2 时追加到初稿提示词末尾。",
        variables=(),
        default="""- mode_type=2 means the keyword field is a required outline, not a short keyword
- Follow the provided outline strictly: preserve heading order, heading levels, and section boundaries
- Do not add, remove, rename, merge, or reorder headings unless the outline is malformed and needs a minimal repair
- Keep SEO/GEO writing quality inside the provided outline instead of inventing a different structure
- Use the brand/product info only as supporting facts, examples, proof, and entity context""",
    ),
    PromptTemplate(
        key="shared.mode2.polish",
        group=GROUP_SHARED,
        name="大纲模式附加要求 · 润色",
        description="mode_type=2 时追加到润色提示词。",
        variables=(),
        default="- mode_type=2: keep the exact heading structure, order, and section boundaries from the current HTML",
    ),
    PromptTemplate(
        key="shared.competitor.default.strategy",
        group=GROUP_SHARED,
        name="竞品策略 · 默认（官网 / 2.0）",
        description="对比类关键词时的竞品处理方式，用于策略阶段。",
        variables=(),
        default=(
                        'If the keyword signals a comparison or alternatives intent (e.g., contains "vs", "versus", "alternatives", "best X for Y", "compare"), do not recommend or name specific competing brands or products in the outline or writing suggestions; compare based on neutral criteria, use-case fit, and objective specifications instead'
        ),
    ),
    PromptTemplate(
        key="shared.competitor.default.draft",
        group=GROUP_SHARED,
        name="竞品策略 · 默认（官网 / 2.0）· 正文",
        description="对比类关键词时的竞品处理方式，用于初稿阶段。",
        variables=(),
        default=(
                        'If the keyword signals a comparison or alternatives intent (e.g., contains "vs", "versus", "alternatives", "best X for Y", "compare"), do not name or recommend specific competing brands or products anywhere in the article body; compare only on neutral criteria, use-case fit, and objective specifications'
        ),
    ),
    PromptTemplate(
        key="shared.competitor.third_party_media.strategy",
        group=GROUP_SHARED,
        name="竞品策略 · 第三方媒体 · 策略",
        description="3.0 且发布场景为第三方媒体时允许点名竞品，用于策略阶段。",
        variables=(),
        default=(
                        'If the keyword signals a comparison or alternatives intent (e.g., contains "vs", "versus", "alternatives", "best X for Y", "compare"), plan a balanced comparison that may name specific competing brands or products; give each candidate clear criteria, trade-offs, and evidence, and do not default to a single-brand recommendation'
        ),
    ),
    PromptTemplate(
        key="shared.competitor.third_party_media.draft",
        group=GROUP_SHARED,
        name="竞品策略 · 第三方媒体 · 正文",
        description="3.0 且发布场景为第三方媒体时允许点名竞品，用于初稿阶段。",
        variables=(),
        default=(
                        'If the keyword signals a comparison or alternatives intent (e.g., contains "vs", "versus", "alternatives", "best X for Y", "compare"), you may name and compare specific competing brands or products in the article body; keep the comparison balanced with clear criteria, trade-offs, and evidence, and do not collapse it into a single-brand recommendation'
        ),
    ),
    PromptTemplate(
        key="shared.competitor.conversion_page.strategy",
        group=GROUP_SHARED,
        name="竞品策略 · 转化页 · 策略",
        description="3.0 且发布场景为转化页时聚焦主推产品，用于策略阶段。",
        variables=(),
        default=(
                        'If the keyword signals a comparison or alternatives intent (e.g., contains "vs", "versus", "alternatives", "best X for Y", "compare"), keep the comparison centered on the primary/named product and the reader\'s buying decision; you may contrast it against alternative categories or objective criteria, but do not recommend or promote specific competing brands as the better choice; keep claims evidence-based without pressure'
        ),
    ),
    PromptTemplate(
        key="shared.competitor.conversion_page.draft",
        group=GROUP_SHARED,
        name="竞品策略 · 转化页 · 正文",
        description="3.0 且发布场景为转化页时聚焦主推产品，用于初稿阶段。",
        variables=(),
        default=(
                        'If the keyword signals a comparison or alternatives intent (e.g., contains "vs", "versus", "alternatives", "best X for Y", "compare"), keep the article body centered on the primary/named product and the reader\'s buying decision; you may compare on objective criteria, fit, and proof points, but do not name competing brands as recommended alternatives; keep the CTA evidence-based and free of exaggerated claims or pressure'
        ),
    ),
)


TEMPLATES_BY_KEY: dict[str, PromptTemplate] = {item.key: item for item in TEMPLATES}
