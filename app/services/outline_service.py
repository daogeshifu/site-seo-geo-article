from __future__ import annotations

from typing import Any

from app.services.llm_client import LLMClient
from app.services.rulebook_service import RulebookService
from app.utils.common import extract_json_object


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
        access_tier: str = "standard",
    ) -> dict[str, Any]:
        normalized_category = (category or "seo").strip().lower()
        normalized_keyword = keyword.strip()
        normalized_info = (info or "").strip()
        normalized_language = (language or "English").strip() or "English"
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
                generation_mode="llm",
            )

        return self._mock_payload(
            category=normalized_category,
            keyword=normalized_keyword,
            info=normalized_info,
            language=normalized_language,
            task_context=normalized_task_context,
            available_links=available_links,
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
    ) -> str:
        mode_name = "GEO" if category == "geo" else "SEO"
        context = rule_context.get("context") or {}
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

Requirements:
{mode_requirements}
- Keep the outline practical, specific, and commercially relevant without sounding like an ad.
- Use the business context and country rules when deciding comparison criteria and examples.
- Use AI Q&A reference answer and adopted source links as GEO research input when provided.
- Only recommend internal links from the allowed list above.
- If a Shopify URL is required, place it naturally in the early buying-intent section.
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
        generation_mode: str,
    ) -> dict[str, Any]:
        writing_suggestions = [
            str(item).strip()
            for item in payload.get("writing_suggestions") or []
            if str(item).strip()
        ]
        if not writing_suggestions:
            writing_suggestions = self._default_writing_suggestions(category, keyword, info, task_context)

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
            outline_markdown = self._default_outline(category, keyword, available_links)

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
    ) -> dict[str, Any]:
        return {
            "category": category,
            "keyword": keyword,
            "info": info,
            "language": language,
            "task_context": task_context,
            "title": keyword,
            "outline_markdown": self._default_outline(category, keyword, available_links),
            "writing_suggestions": self._default_writing_suggestions(category, keyword, info, task_context),
            "recommended_internal_links": self._default_internal_links(available_links),
            "generation_mode": "mock",
        }

    def _default_outline(self, category: str, keyword: str, available_links: list[dict[str, str]]) -> str:
        answer_label = "Quick Answer" if category == "geo" else "Intro"
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
        return f"""# {keyword}

## Introductie
{quick_answer_instruction}
- Leg kort uit voor wie dit onderwerp relevant is.
{product_line}

## Wat betekent deze zoekvraag precies?
- Definieer de belangrijkste term of het besliskader.
- Leg uit welke factoren het antwoord beïnvloeden.

## Belangrijkste vergelijking of besliscriteria
- Benoem 3-5 hoofdcriteria.
- Houd deze sectie scanbaar en feitelijk.

## Welke oplossing past het best bij welke situatie?
- Verdeel dit in duidelijke subsecties per gebruikssituatie.
- Koppel waar relevant naar een officiële interne pagina.

## Aandachtspunten vóór je kiest
- Benoem grenzen, randvoorwaarden of compatibiliteit.
- Voeg nuance toe zodat de tekst geloofwaardig blijft.

## Conclusie
- Vat het antwoord kort samen.
- Sluit af met een natuurlijke CTA.

## FAQ
### Veelgestelde vraag 1
### Veelgestelde vraag 2
### Veelgestelde vraag 3

## {source_label}
- Gebruik alleen officiële of vooraf opgegeven interne links.
- Noem alleen verifieerbare claims en specificaties.
""".strip()

    def _default_writing_suggestions(
        self,
        category: str,
        keyword: str,
        info: str,
        task_context: dict[str, Any],
    ) -> list[str]:
        country = str(task_context.get("country") or "").upper()
        suggestions = [
            f"Open met een direct antwoord op '{keyword}' in de eerste 100-150 woorden.",
            "Gebruik korte, scanbare H2-secties en vermijd generieke tussenkoppen.",
            "Werk met concrete criteria, zodat de lezer en AI-systemen het antwoord makkelijk kunnen samenvatten.",
        ]
        if info:
            suggestions.append("Verwerk merk-, product- of businesscontext alleen waar die het besluit van de lezer echt ondersteunt.")
        if country:
            suggestions.append(f"Houd voorbeelden, termen en nuance consistent met de marktcontext voor {country}.")
        if category == "geo":
            suggestions.extend(
                [
                    "Voeg een duidelijke bronnen- of verificatiesectie toe voor claims en productspecificaties.",
                    "Maak de FAQ anders dan de hoofdtekst en laat elk antwoord een echte vervolgquery afdekken.",
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
