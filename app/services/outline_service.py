from __future__ import annotations

from typing import Any

from app.services.llm_client import LLMClient
from app.services.prompt_builder import _ai_answer_data_guidance, _body_structure_limits, _cta_guidance
from app.services.prompt_store import get_prompt_store
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
        store = get_prompt_store()
        return store.render(
            "outline.v2",
            mode_name=mode_name,
            keyword=keyword,
            info_block=info or "No extra business context provided.",
            language=language,
            task_context_block="\n".join(f"- {item}" for item in market_notes),
            link_lines=link_lines,
            ai_answer_guidance=_ai_answer_data_guidance(category),
            cta_guidance=_cta_guidance(category),
            mode_requirements=store.render(f"outline.mode.{'geo' if category == 'geo' else 'seo'}"),
            word_limit=word_limit,
            max_h2=limits["max_h2"],
            max_h3=limits["max_h3"],
            faq_count=limits["faq_count"],
        )

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
        if publishing_context not in {"official_website", "third_party_media", "conversion_page"}:
            publishing_context = "official_website"
        store = get_prompt_store()
        return store.render(
            "outline.v3",
            mode_name=mode_name,
            keyword=keyword,
            info_block=info or "No extra business context provided.",
            language=language,
            publishing_note=store.render(f"outline.publishing.{publishing_context}"),
            country=context.get("country") or "not specified",
            market=context.get("market") or "not specified",
            locale=rule_context.get("locale_variant") or language,
            ai_qa_content=context.get("ai_qa_content") or "not provided",
            ai_qa_source=context.get("ai_qa_source") or "not provided",
            shopify_note=(
                rule_context.get("shopify_url")
                if rule_context.get("requires_shopify_link") and rule_context.get("shopify_url")
                else "no"
            ),
            link_lines=link_lines,
            ai_answer_guidance=_ai_answer_data_guidance(category),
            cta_guidance=_cta_guidance(category),
            h2_min=h2_min,
            h2_max=h2_max,
            faq_count=faq_count,
        )

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
            "- Begin de openingsalinea met **Kort antwoord:** gevolgd door een direct antwoord in 2-3 zinnen (geen apart kopje)."
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
