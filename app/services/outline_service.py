from __future__ import annotations

from typing import Any

from app.services.llm_client import LLMClient
from app.services.prompt_builder import _ai_answer_data_guidance, _body_structure_limits, _cta_guidance
from app.services.rulebook_service import RulebookService
from app.utils.common import extract_json_object


def _v3_outline_limits(word_limit: int) -> tuple[int, int, int]:
    _ = word_limit
    return 5, 7, 6


class OutlineService:
    def __init__(self, llm_client: LLMClient, rulebook_service: RulebookService | None = None) -> None:
        self.llm_client = llm_client
        self.rulebook_service = rulebook_service or RulebookService()

    def generate(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        task_context: dict[str, Any] | None = None,
        language: str = "English",
        provider: str = "openai",
        word_limit: int = 1200,
        access_tier: str = "standard",
    ) -> dict[str, Any]:
        normalized_category = (category or "seo").strip().lower()
        normalized_keyword = keyword.strip()
        normalized_info = (info or "").strip()
        normalized_language = (language or "English").strip() or "English"
        normalized_word_limit = max(200, int(word_limit))
        normalized_task_context = self.rulebook_service.normalize_task_context(task_context)
        rule_context = self.rulebook_service.resolve_rules(
            category=normalized_category,
            language=normalized_language,
            task_context=normalized_task_context,
        )
        available_links = self._available_links(rule_context)

        if not normalized_keyword:
            raise ValueError("keyword is required")

        if self.llm_client.enabled(provider):
            prompt = self._build_prompt(
                category=normalized_category,
                keyword=normalized_keyword,
                info=normalized_info,
                language=normalized_language,
                rule_context=rule_context,
                available_links=available_links,
                word_limit=normalized_word_limit,
            )
            raw = self.llm_client.complete(
                prompt,
                expect_json=True,
                access_tier=access_tier,
                provider=provider,
            )
            payload = extract_json_object(raw)
            return self._normalize_payload(
                payload,
                category=normalized_category,
                keyword=normalized_keyword,
                info=normalized_info,
                language=normalized_language,
                task_context=normalized_task_context,
                available_links=available_links,
                word_limit=normalized_word_limit,
                generation_mode="llm",
            )

        return self._mock_payload(
            category=normalized_category,
            keyword=normalized_keyword,
            info=normalized_info,
            language=normalized_language,
            task_context=normalized_task_context,
            available_links=available_links,
            word_limit=normalized_word_limit,
        )

    def _build_prompt(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        language: str,
        rule_context: dict[str, Any],
        available_links: list[dict[str, str]],
        word_limit: int,
    ) -> str:
        mode_name = "GEO" if category == "geo" else "SEO"
        limits = _body_structure_limits(word_limit)
        context = rule_context.get("context") or {}
        if str(context.get("content_version") or "2.0") == "3.0":
            return self._build_v3_prompt(
                category=category,
                keyword=keyword,
                info=info,
                language=language,
                rule_context=rule_context,
                available_links=available_links,
                word_limit=word_limit,
            )
        link_lines = (
            "\n".join(f"- {item['label']}: {item['url']}" for item in available_links)
            or "- No official internal links provided"
        )
        market_notes = [
            f"Country: {context.get('country') or 'not specified'}",
            f"Market: {context.get('market') or 'not specified'}",
            f"Locale: {rule_context.get('locale_variant') or language}",
            f"AI Q&A reference answer: {context.get('ai_qa_content') or 'not provided'}",
            f"AI Q&A adopted source links: {context.get('ai_qa_source') or 'not provided'}",
            (
                f"Shopify URL required: {rule_context.get('shopify_url')}"
                if rule_context.get("requires_shopify_link") and rule_context.get("shopify_url")
                else "Shopify URL requirement: no"
            ),
        ]
        mode_requirements = (
            "- Optimize for answer-first extraction, AI readability, clear entities, FAQ, citations, and trust signals.\n"
            "- Make the outline directly usable for a GEO article.\n"
            "- The opening should answer the query quickly.\n"
            "- Include sections for sources/verification and FAQ."
            if category == "geo"
            else
            "- Optimize for search intent alignment, H1/H2/H3 structure, natural keyword coverage, readability, and internal linking.\n"
            "- Make the outline directly usable for an SEO article.\n"
            "- Include a strong intro, clear section hierarchy, conclusion, and FAQ."
        )
        ai_answer_guidance = _ai_answer_data_guidance(category)
        cta_guidance = _cta_guidance(category)
        info_block = info or "No extra business context provided."
        return f"""
You are a senior {mode_name} content strategist.
Create a clean article outline plan for the keyword below.

Keyword:
{keyword}

Business context:
{info_block}

Language:
{language}

Task context:
{chr(10).join(f"- {item}" for item in market_notes)}

Allowed internal links:
{link_lines}

AI-answer-data writing guidance:
{ai_answer_guidance}

{cta_guidance}

        Requirements:
{mode_requirements}
- Target approximately {word_limit} words/characters of textual content in the final article.
- For this target length, keep the outline body within {limits["max_h2"]} H2 sections and {limits["max_h3"]} H3 subsections total.
- Only use H3 when it materially improves clarity; do not add H3 by default.
- FAQ should contain {limits["faq_count"]} natural questions for this target length.
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
{{
  "title": "",
  "outline_markdown": "",
  "writing_suggestions": ["", "", ""],
  "recommended_internal_links": [
    {{
      "label": "",
      "url": "",
      "reason": ""
    }}
  ]
}}
""".strip()

    def _build_v3_prompt(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        language: str,
        rule_context: dict[str, Any],
        available_links: list[dict[str, str]],
        word_limit: int,
    ) -> str:
        mode_name = "GEO" if category == "geo" else "SEO"
        context = rule_context.get("context") or {}
        publishing_context = str(context.get("publishing_context") or "official_website")
        h2_min, h2_max, faq_count = _v3_outline_limits(word_limit)
        link_lines = (
            "\n".join(f"- {item['label']}: {item['url']}" for item in available_links)
            or "- No official internal links provided"
        )
        publishing_notes = {
            "official_website": (
                "official_website: first-party brand article. Prioritize the provided brand/product when the input supports it. "
                "Avoid competitor recommendations unless the keyword explicitly requires comparison; compare competitors only through objective specs, criteria, and fit."
            ),
            "third_party_media": (
                "third_party_media: neutral editorial article. Use balanced comparison, objective criteria, evidence, and clear pros/cons. Competitors or alternatives may be named when relevant."
            ),
            "conversion_page": (
                "conversion_page: buying-decision or landing-page content. Make the primary product, fit scenario, proof points, and CTA clearer, while avoiding exaggerated claims or pressure."
            ),
        }
        ai_answer_guidance = _ai_answer_data_guidance(category)
        cta_guidance = _cta_guidance(category)
        info_block = info or "No extra business context provided."
        return f"""
You are a senior {mode_name} content strategist.
Create a version 3.0 article outline.

Keyword:
{keyword}

Business context:
{info_block}

Language:
{language}

Publishing context:
{publishing_notes.get(publishing_context, publishing_notes["official_website"])}

Task context:
- Country: {context.get('country') or 'not specified'}
- Market: {context.get('market') or 'not specified'}
- Locale: {rule_context.get('locale_variant') or language}
- AI Q&A reference answer: {context.get('ai_qa_content') or 'not provided'}
- AI Q&A adopted source links: {context.get('ai_qa_source') or 'not provided'}
- Shopify URL required: {rule_context.get('shopify_url') if rule_context.get('requires_shopify_link') and rule_context.get('shopify_url') else 'no'}

Allowed internal links:
{link_lines}

AI-answer-data writing guidance:
{ai_answer_guidance}

{cta_guidance}

Version 3.0 outline style:
- Keep the outline compact and high-signal. Do not create a detailed paragraph-by-paragraph writing plan.
- outline_markdown must be a short line-based skeleton only, not a full SEO brief.
- Use exactly this output shape inside outline_markdown:
  H1: ...
  H2: ... - coverage query: "..."
  H2: ... - decision factor: "..."
  FAQ ({faq_count} questions)
  Internal Links: ...
- Do not include URL, slug, SEO title, meta description, intro notes, section descriptions, Markdown heading syntax (# or ##), or bullets under each H2 inside outline_markdown.
- Plan {h2_min}-{h2_max} H2 lines only. Use no H3 sections unless the keyword explicitly requires grouped subtopics.
- Each H2 must be one line only and should include one concise intent note such as: coverage query, user question, comparison angle, proof source, review source, or decision factor.
- Include a "Quick Verdict (TL;DR)" or equivalent early H2 for comparison, buying-decision, and GEO topics.
- Include a side-by-side specs or criteria table section when the topic compares products, models, specs, or options.
- Include review/evidence summary sections only when sources are provided or named in the input; do not invent source names.
- FAQ should be listed as "FAQ ({faq_count} questions)" rather than writing every FAQ answer in the outline.
- Internal links should be listed by page type or provided URL label; use only allowed internal links when URLs are provided.
- If brand/product info is provided, include one H2 or FAQ angle that explains when the named product/model/solution is a logical option.
- Keep product recommendations scenario-bound. Do not call a product the universal best choice.
- Return an outline a writer can use immediately, but keep outline_markdown close to the compact example style rather than a detailed plan.

Return strict JSON only:
{{
  "title": "",
  "outline_markdown": "",
  "writing_suggestions": ["", "", ""],
  "recommended_internal_links": [
    {{
      "label": "",
      "url": "",
      "reason": ""
    }}
  ]
}}
""".strip()

    def _normalize_payload(
        self,
        payload: dict[str, Any],
        *,
        category: str,
        keyword: str,
        info: str,
        language: str,
        task_context: dict[str, Any],
        available_links: list[dict[str, str]],
        word_limit: int,
        generation_mode: str,
    ) -> dict[str, Any]:
        writing_suggestions = [
            str(item).strip()
            for item in payload.get("writing_suggestions") or []
            if str(item).strip()
        ]
        if not writing_suggestions:
            writing_suggestions = self._default_writing_suggestions(category, keyword, info, task_context, word_limit)

        allowed_urls = {item["url"] for item in available_links if item.get("url")}
        recommended_internal_links = []
        for item in payload.get("recommended_internal_links") or []:
            url = str(item.get("url") or "").strip()
            label = str(item.get("label") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not url or url not in allowed_urls:
                continue
            recommended_internal_links.append(
                {
                    "label": label or self._label_for_url(url, available_links),
                    "url": url,
                    "reason": reason or "Recommended because it matches the allowed internal link set.",
                }
            )

        if not recommended_internal_links:
            recommended_internal_links = self._default_internal_links(available_links)

        outline_markdown = str(payload.get("outline_markdown") or "").strip()
        if not outline_markdown:
            outline_markdown = self._default_outline(category, keyword, available_links, word_limit, task_context)

        return {
            "category": category,
            "keyword": keyword,
            "info": info,
            "language": language,
            "task_context": task_context,
            "title": str(payload.get("title") or keyword).strip() or keyword,
            "outline_markdown": outline_markdown,
            "writing_suggestions": writing_suggestions,
            "recommended_internal_links": recommended_internal_links,
            "generation_mode": generation_mode,
        }

    def _mock_payload(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        language: str,
        task_context: dict[str, Any],
        available_links: list[dict[str, str]],
        word_limit: int,
    ) -> dict[str, Any]:
        return {
            "category": category,
            "keyword": keyword,
            "info": info,
            "language": language,
            "task_context": task_context,
            "title": keyword,
            "outline_markdown": self._default_outline(category, keyword, available_links, word_limit, task_context),
            "writing_suggestions": self._default_writing_suggestions(category, keyword, info, task_context, word_limit),
            "recommended_internal_links": self._default_internal_links(available_links),
            "generation_mode": "mock",
        }

    def _default_outline(
        self,
        category: str,
        keyword: str,
        available_links: list[dict[str, str]],
        word_limit: int,
        task_context: dict[str, Any] | None = None,
    ) -> str:
        if str((task_context or {}).get("content_version") or "2.0") == "3.0":
            return self._default_v3_outline(keyword, available_links, word_limit)
        limits = _body_structure_limits(word_limit)
        source_label = "Bronnen en verificatie" if category == "geo" else "Aanbevolen interne links"
        first_link = next((item["url"] for item in available_links if item.get("url")), "")
        product_line = (
            f"- Link vroeg in het artikel naar: {first_link}"
            if first_link
            else "- Voeg vroeg in het artikel een relevante interne productlink toe."
        )
        quick_answer_instruction = (
            "- Begin de openingsalinea met **Quick Answer:** gevolgd door een direct antwoord in 2-3 zinnen (geen apart kopje)."
            if category == "geo"
            else "- Beantwoord de hoofdvraag in 2-3 zinnen."
        )
        body_sections = [
            (
                "Wat betekent deze zoekvraag precies?",
                "- Definieer de belangrijkste term of het besliskader.\n- Leg uit welke factoren het antwoord beïnvloeden.",
            ),
            (
                "Belangrijkste vergelijking of besliscriteria",
                "- Benoem 3-5 hoofdcriteria.\n- Houd deze sectie scanbaar en feitelijk.",
            ),
            (
                "Welke oplossing past het best bij welke situatie?",
                "- Verdeel dit in duidelijke subsecties per gebruikssituatie.\n- Koppel waar relevant naar een officiële interne pagina.",
            ),
            (
                "Aandachtspunten vóór je kiest",
                "- Benoem grenzen, randvoorwaarden of compatibiliteit.\n- Voeg nuance toe zodat de tekst geloofwaardig blijft.",
            ),
            (
                "Veelgemaakte misverstanden of fouten",
                "- Benoem welke aannames vaak tot een verkeerde keuze leiden.\n- Corrigeer ze kort en feitelijk.",
            ),
        ]
        faq_lines = "\n".join(f"### Veelgestelde vraag {index}" for index in range(1, limits["faq_count"] + 1))
        body_lines: list[str] = []
        for title, bullet_block in body_sections[: limits["max_h2"]]:
            body_lines.append(f"## {title}")
            body_lines.append(bullet_block)
        if limits["max_h3"] > 0:
            body_lines.append("### Verdere nuance of subvraag")
            body_lines.append("- Gebruik alleen een H3 als die echt helpt om een beslispunt te verduidelijken.")

        return f"""# {keyword}

## Introductie
{quick_answer_instruction}
- Leg kort uit voor wie dit onderwerp relevant is.
{product_line}

{chr(10).join(body_lines)}

## Conclusie
- Vat het antwoord kort samen.
- Sluit af met een zachte CTA: benoem de situatie van de lezer, noem welke specificaties of voorwaarden vergeleken moeten worden en maak duidelijk welke waarde die stap oplevert.

## FAQ
{faq_lines}

## {source_label}
- Gebruik alleen officiële of vooraf opgegeven interne links.
- Noem alleen verifieerbare claims en specificaties.
""".strip()

    def _default_v3_outline(
        self,
        keyword: str,
        available_links: list[dict[str, str]],
        word_limit: int,
    ) -> str:
        _h2_min, h2_max, faq_count = _v3_outline_limits(word_limit)
        base_sections = [
            ("Quick Verdict (TL;DR)", 'coverage query: "which option is the better fit and why"'),
            ("Specs Comparison Table (Side-by-Side)", 'coverage query: "compare specs, capacity, output, charging, price, warranty"'),
            ("Battery Life and Long-Term Value", 'coverage query: "cycle life, warranty, long-term investment"'),
            ("Charging Speed and Real-World Convenience", 'coverage query: "charging time, alternator or solar advantage, daily use"'),
            ("Running Key Appliances or Core Use Cases", 'coverage query: "peak output, air conditioner, fridge, off-grid caravan use"'),
            ("Expandability for Long-Term Use", 'coverage query: "expandable capacity, accessories, future upgrade path"'),
            ("What Real Users and Reviews Say", 'coverage query: "review summary, user feedback, evidence gaps"'),
            ("Who Should Choose This Option", 'coverage query: "best-fit scenarios, poor-fit scenarios, what to verify first"'),
            ("Final Buying Checklist", 'coverage query: "usage, budget, installation, specs, internal next step"'),
        ]
        section_lines = "\n".join(f"H2: {title} - {note}" for title, note in base_sections[:h2_max])
        link_lines = ", ".join(item["label"] for item in available_links if item.get("label")) or "Product PDP, bundle page, compare specs page"
        return f"""H1: {keyword}
{section_lines}
FAQ ({faq_count} questions)
Internal Links: {link_lines}
""".strip()

    def _default_writing_suggestions(
        self,
        category: str,
        keyword: str,
        info: str,
        task_context: dict[str, Any],
        word_limit: int,
    ) -> list[str]:
        country = str(task_context.get("country") or "").upper()
        limits = _body_structure_limits(word_limit)
        if str(task_context.get("content_version") or "2.0") == "3.0":
            _h2_min, h2_max, faq_count = _v3_outline_limits(word_limit)
            return [
                f"Use version 3.0 outline style: H1, compact H2 lines with coverage notes, FAQ ({faq_count} questions), and Internal Links.",
                f"Keep the outline concise and high-signal with no more than {h2_max} H2 sections.",
                "Add coverage notes for search intent, subqueries, proof sources, reviews, comparison angles, or decision factors.",
                "If product context is provided, include a scenario-bound product-fit angle without calling it the universal best choice.",
                "Use the selected publishing context to tune neutrality, first-party product emphasis, and CTA strength.",
            ]
        suggestions = [
            f"Open met een direct antwoord op '{keyword}' in de eerste 100-150 woorden.",
            (
                f"Gebruik korte, scanbare H2-secties en houd de body voor deze lengte binnen "
                f"{limits['max_h2']} H2-koppen en {limits['max_h3']} H3-koppen."
            ),
            "Werk met concrete criteria, zodat de lezer en AI-systemen het antwoord makkelijk kunnen samenvatten.",
            "Plan de afsluitende CTA rond de situatie van de lezer, een concrete volgende stap en de praktische waarde daarvan.",
            "Als er productcontext is, voeg een FAQ toe over wanneer die optie logisch is en welke voorwaarden eerst gecontroleerd moeten worden.",
        ]
        if info:
            suggestions.append("Verwerk merk-, product- of businesscontext alleen waar die het besluit van de lezer echt ondersteunt.")
        if country:
            suggestions.append(f"Houd voorbeelden, termen en nuance consistent met de marktcontext voor {country}.")
        if category == "geo":
            suggestions.extend(
                [
                    "Voeg een duidelijke bronnen- of verificatiesectie toe voor claims en productspecificaties.",
                    f"Maak de FAQ anders dan de hoofdtekst en houd die voor deze lengte bij {limits['faq_count']} natuurlijke vervolgvragen.",
                ]
            )
        else:
            suggestions.extend(
                [
                    "Verwerk het hoofdkeyword natuurlijk in H1, intro, minstens één H2 en de conclusie.",
                    "Plaats het belangrijkste interne productlink vroeg in het artikel voor een sterkere SEO-structuur.",
                ]
            )
        return suggestions[:5]

    def _default_internal_links(self, available_links: list[dict[str, str]]) -> list[dict[str, str]]:
        if not available_links:
            return []
        links: list[dict[str, str]] = []
        for index, item in enumerate(available_links, start=1):
            links.append(
                {
                    "label": item.get("label") or f"Internal link {index}",
                    "url": item.get("url") or "",
                    "reason": "Gebruik als vroege productlink of ondersteunende interne verwijzing.",
                }
            )
        return [item for item in links if item["url"]]

    def _available_links(self, rule_context: dict[str, Any]) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        shopify_url = str(rule_context.get("shopify_url") or "").strip()
        if shopify_url:
            links.append({"label": "Shopify product page", "url": shopify_url})
        for item in rule_context.get("resolved_internal_links") or []:
            label = str(item.get("label") or "").strip()
            url = str(item.get("url") or "").strip()
            if label and url and not any(existing["url"] == url for existing in links):
                links.append({"label": label, "url": url})
        return links

    @staticmethod
    def _label_for_url(url: str, available_links: list[dict[str, str]]) -> str:
        for item in available_links:
            if item.get("url") == url:
                return item.get("label") or url
        return url
