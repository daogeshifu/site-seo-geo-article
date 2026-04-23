from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from app.services.article_validator import ArticleValidator
from app.services.image_service import ImageService
from app.services.llm_client import LLMClient
from app.services.prompt_builder import (
    build_draft_prompt,
    build_polish_prompt,
    build_strategy_prompt,
)
from app.services.rulebook_service import RulebookService
from app.utils.common import extract_json_object, slugify, truncate


class WriterService:
    def __init__(
        self,
        llm_client: LLMClient,
        image_service: ImageService | None = None,
        rulebook_service: RulebookService | None = None,
        article_validator: ArticleValidator | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.image_service = image_service
        self.rulebook_service = rulebook_service or RulebookService()
        self.article_validator = article_validator or ArticleValidator()

    def generate(
        self,
        *,
        asset_namespace: str,
        category: str,
        keyword: str,
        mode_type: int = 1,
        info: str,
        task_context: dict[str, Any] | None = None,
        language: str = "English",
        provider: str = "openai",
        word_limit: int = 1200,
        access_tier: str = "standard",
        include_cover: int = 1,
        content_image_count: int = 3,
    ) -> dict[str, Any]:
        normalized_mode_type = 2 if int(mode_type) == 2 else 1
        normalized_word_limit = max(200, int(word_limit))
        normalized_context = self.rulebook_service.normalize_task_context(task_context)
        rule_context = self.rulebook_service.resolve_rules(
            category=category,
            language=language,
            task_context=normalized_context,
        )

        if self.llm_client.enabled(provider):
            strategy_prompt = build_strategy_prompt(
                category,
                keyword,
                info,
                language,
                rule_context,
                normalized_mode_type,
            )
            raw_strategy = self.llm_client.complete(
                strategy_prompt,
                expect_json=True,
                access_tier=access_tier,
                provider=provider,
            )
            strategy = extract_json_object(raw_strategy)

            draft_prompt = build_draft_prompt(
                category,
                keyword,
                info,
                language,
                strategy,
                rule_context,
                normalized_word_limit,
                normalized_mode_type,
            )
            draft_html = self.llm_client.complete(draft_prompt, access_tier=access_tier, provider=provider)

            polish_prompt = build_polish_prompt(
                category,
                language,
                keyword,
                draft_html,
                rule_context,
                normalized_word_limit,
                normalized_mode_type,
            )
            polished_html = self.llm_client.complete(polish_prompt, access_tier=access_tier, provider=provider)

            article = self._package_article(
                category=category,
                keyword=keyword,
                info=info,
                task_context=normalized_context,
                language=language,
                mode_type=normalized_mode_type,
                strategy=strategy,
                rule_context=rule_context,
                html=polished_html.strip(),
                generation_mode="llm",
                word_limit=normalized_word_limit,
            )
        else:
            article = self._mock_article(
                category=category,
                keyword=keyword,
                info=info,
                task_context=normalized_context,
                language=language,
                mode_type=normalized_mode_type,
                word_limit=normalized_word_limit,
            )

        article = self.article_validator.apply(
            article,
            category=category,
            keyword=str(article.get("title") or keyword) if normalized_mode_type == 2 else keyword,
            rule_context=rule_context,
        )
        return self._attach_images(
            asset_namespace=asset_namespace,
            article=article,
            category=category,
            keyword=keyword,
            mode_type=normalized_mode_type,
            info=info,
            include_cover=include_cover,
            content_image_count=content_image_count,
        )

    def ensure_images(
        self,
        *,
        asset_namespace: str,
        article: dict[str, Any],
        category: str,
        keyword: str,
        mode_type: int = 1,
        info: str,
        include_cover: int = 1,
        content_image_count: int = 3,
    ) -> dict[str, Any]:
        return self._attach_images(
            asset_namespace=asset_namespace,
            article=article,
            category=category,
            keyword=keyword,
            mode_type=mode_type,
            info=info,
            include_cover=include_cover,
            content_image_count=content_image_count,
        )

    def present_article(
        self,
        *,
        asset_namespace: str,
        article: dict[str, Any],
        include_cover: int,
        content_image_count: int,
    ) -> dict[str, Any]:
        response_article = deepcopy(article)
        stored_assets = response_article.get("images") or []
        response_assets = (
            self.image_service.build_response_assets(
                stored_assets,
                asset_namespace=asset_namespace,
                include_cover=include_cover,
                content_image_count=content_image_count,
            )
            if self.image_service
            else []
        )
        raw_html = response_article.get("raw_html") or (
            self.image_service.strip_generated_images(response_article.get("html", ""))
            if self.image_service
            else response_article.get("html", "")
        )
        response_article["raw_html"] = raw_html
        response_article["images"] = response_assets
        response_article["cover_image"] = next((item for item in response_assets if item["role"] == "cover"), None)
        response_article["content_images"] = [item for item in response_assets if item["role"] == "content"]
        response_article["html"] = (
            self.image_service.inject_images_into_html(raw_html, response_assets)
            if self.image_service
            else raw_html
        )
        response_article["image_generation_mode"] = (
            response_article.get("image_generation_mode")
            if response_assets
            else "disabled"
        )
        return response_article

    def _package_article(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        task_context: dict[str, Any] | None,
        language: str,
        mode_type: int,
        strategy: dict[str, Any],
        rule_context: dict[str, Any],
        html: str,
        generation_mode: str,
        word_limit: int,
    ) -> dict[str, Any]:
        title = (
            (strategy.get("h1_options") or [keyword])[0]
            if isinstance(strategy.get("h1_options"), list)
            else keyword
        )
        return {
            "category": category,
            "keyword": keyword,
            "mode_type": 2 if int(mode_type) == 2 else 1,
            "language": language,
            "task_context": task_context or {},
            "title": title,
            "meta_title": truncate(strategy.get("meta_title") or title, int(rule_context.get("meta_title_limit", 60))),
            "meta_description": truncate(
                strategy.get("meta_description")
                or f"{keyword} article for {info or 'your brand'}",
                int(rule_context.get("meta_description_limit", 160)),
            ),
            "slug": slugify(title),
            "raw_html": html,
            "html": html,
            "strategy": strategy,
            "rule_context": rule_context,
            "generation_mode": generation_mode,
            "word_limit": int(word_limit),
            "images": [],
            "cover_image": None,
            "content_images": [],
            "image_generation_mode": "disabled",
        }

    def _mock_article(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        task_context: dict[str, Any] | None,
        language: str,
        mode_type: int,
        word_limit: int,
    ) -> dict[str, Any]:
        brand_line = info.strip() or "Use your real brand, product facts, and proof here."
        rule_context = self.rulebook_service.resolve_rules(
            category=category,
            language=language,
            task_context=task_context,
        )
        internal_link = (
            f'<a href="{rule_context["shopify_url"]}">official product page</a>'
            if rule_context.get("shopify_url")
            else "official product page"
        )
        normalized_mode_type = 2 if int(mode_type) == 2 else 1

        if normalized_mode_type == 2:
            h1_title, outline = self._extract_outline_structure(keyword)
            if not outline:
                outline = [
                    {"level": "H2", "title": f"{h1_title} overview"},
                    {"level": "H2", "title": "Key points"},
                ]

            faq_questions = [item["title"] for item in outline if item["title"].endswith("?")][:4]
            if category == "seo":
                strategy = {
                    "intent": "outline-driven article writing",
                    "audience": "readers expecting the provided outline to be expanded clearly",
                    "meta_title": truncate(h1_title, int(rule_context["meta_title_limit"])),
                    "meta_description": truncate(
                        f"Outline-based SEO article for {h1_title} that follows the supplied structure closely.",
                        int(rule_context["meta_description_limit"]),
                    ),
                    "h1_options": [h1_title],
                    "outline": outline,
                    "longtail_keywords": [h1_title],
                    "faq_questions": faq_questions,
                    "image_briefs": [f"Editorial image for {h1_title}"],
                    "link_opportunities": ["Use official product or support pages where relevant"],
                    "compliance_notes": rule_context.get("required_notes", []),
                    "internal_link_plan": rule_context.get("resolved_internal_links", []),
                }
            else:
                strategy = {
                    "search_intent": "outline-driven answer content",
                    "audience": "readers expecting a concise answer that follows the supplied outline",
                    "meta_title": truncate(h1_title, int(rule_context["meta_title_limit"])),
                    "meta_description": truncate(
                        f"Outline-based GEO article for {h1_title} that follows the supplied structure closely.",
                        int(rule_context["meta_description_limit"]),
                    ),
                    "answer_first_summary": f"The short answer to {h1_title} should stay consistent with the supplied outline.",
                    "entity_summary": brand_line,
                    "h1_options": [h1_title],
                    "outline": outline,
                    "claim_blocks": [],
                    "faq_questions": faq_questions,
                    "reference_plan": ["Use official or verifiable sources that match the supplied outline"],
                    "internal_link_plan": rule_context.get("resolved_internal_links", []),
                    "compliance_notes": rule_context.get("required_notes", []),
                    "schema_suggestions": ["Article", "FAQPage"],
                    "trust_signals": ["author byline", "publish date", "last updated", "references"],
                    "image_briefs": [f"Editorial image for {h1_title}"],
                }

            html_parts = [f"<h1>{h1_title}</h1>"]
            if category == "seo":
                html_parts.append(
                    f"<p>This draft follows the supplied outline for {h1_title} and expands each section without changing the requested structure.</p>"
                )
                html_parts.append(
                    f"<p>Use the {internal_link} where it helps the reader, and keep brand context supportive instead of promotional.</p>"
                )
            else:
                html_parts.append(
                    f"<p>The short answer for {h1_title} should be stated clearly first, then expanded strictly within the supplied outline.</p>"
                )
                html_parts.append(
                    f"<p>Use direct, evidence-aware language and point readers to the {internal_link} when an official reference helps validate the answer.</p>"
                )

            for item in outline:
                tag = item["level"].lower()
                title = item["title"]
                html_parts.append(f"<{tag}>{title}</{tag}>")
                if category == "seo":
                    html_parts.append(
                        f"<p>This section expands on {title} while keeping the original outline order and intent intact for {h1_title}.</p>"
                    )
                    html_parts.append(
                        "<p>Add concrete examples, search-intent detail, and brand-specific proof only when they directly support this outline section.</p>"
                    )
                else:
                    html_parts.append(
                        f"<p>This section answers {title} in a concise, extractable way and keeps the entity framing consistent with {h1_title}.</p>"
                    )
                    html_parts.append(
                        "<p>Support the key claims here with source types, product facts, or policy references that match this outline section.</p>"
                    )

            return self._package_article(
                category=category,
                keyword=keyword,
                info=info,
                task_context=task_context,
                language=language,
                mode_type=normalized_mode_type,
                strategy=strategy,
                rule_context=rule_context,
                html="\n".join(html_parts).strip(),
                generation_mode="mock",
                word_limit=word_limit,
            )

        if category == "seo":
            strategy = {
                "intent": "informational with commercial support",
                "audience": "buyers researching the topic before making a decision",
                "meta_title": truncate(f"{keyword} Guide for Better Rankings", int(rule_context["meta_title_limit"])),
                "meta_description": truncate(
                    f"Learn how to write about {keyword} with a clear SEO structure, natural keyword placement, and a stronger conversion path.",
                    int(rule_context["meta_description_limit"]),
                ),
                "h1_options": [f"{keyword}: A Practical SEO Content Guide"],
                "outline": [
                    {"level": "H2", "title": f"What {keyword} really means for search intent"},
                    {"level": "H2", "title": f"How to structure a strong {keyword} article"},
                    {"level": "H2", "title": "How brand and product context can strengthen the content"},
                    {"level": "H2", "title": "Common mistakes that weaken rankings"},
                    {"level": "H2", "title": "Conclusion"},
                    {"level": "H2", "title": "FAQ"},
                ],
                "faq_questions": [
                    f"How many times should {keyword} appear in the article?",
                    f"How long should a {keyword} article be?",
                    "How can product information be added naturally?",
                ],
                "image_briefs": [
                    f"Hero image illustrating {keyword}",
                    "Process diagram showing article structure",
                ],
                "link_opportunities": [
                    "Anchor to buying guide or product comparison page",
                    "Anchor to documentation or category page",
                ],
                "compliance_notes": rule_context.get("required_notes", []),
                "internal_link_plan": rule_context.get("resolved_internal_links", []),
            }
            html = f"""
<h1>{strategy["h1_options"][0]}</h1>
<p>{keyword} content performs best when it solves the reader's question immediately, keeps the structure clean, and uses product context only where it adds real value. This demo article is a scaffold, but it already follows the same three-step idea from your PHP flow: strategy first, drafting second, polishing third.</p>
<p>When readers need specifics, send them to the {internal_link} early instead of hiding important product details until the end.</p>
<h2>What {keyword} really means for search intent</h2>
<p>Before writing, clarify whether the query is informational, commercial, or comparison-driven. That decision affects the article angle, the H2 structure, and even how aggressive the product mentions should be. A page that tries to do everything at once usually ends up ranking for nothing important.</p>
<p>For most SEO workflows, the safest starting point is to answer the main question quickly, then expand with deeper sections that cover related concerns, objections, and next steps. This keeps the article useful to both search engines and real readers.</p>
<h2>How to structure a strong {keyword} article</h2>
<p>A strong structure starts with one H1, a direct introduction, and a sequence of H2 and H3 sections that move from basic explanation to practical detail. Each paragraph should stay short enough to scan easily, especially on mobile.</p>
<ul>
  <li><strong>Meta title:</strong> keep it concise and close to the core keyword.</li>
  <li><strong>Meta description:</strong> clarify the article promise and support click-through.</li>
  <li><strong>FAQ:</strong> use 2-4 real follow-up questions near the end.</li>
</ul>
<h2>How brand and product context can strengthen the content</h2>
<p>Brand and product context should sharpen the article, not hijack it. Use concrete facts, positioning, or use cases only when they help the reader understand why one option is more relevant than another.</p>
<p><strong>Suggested brand context:</strong> {brand_line}</p>
<h2>Common mistakes that weaken rankings</h2>
<p>The biggest issues are keyword stuffing, vague headings, and introductions that take too long to deliver value. Another common problem is writing generic copy that could belong to any brand in any category. Specificity is almost always the faster path to better performance.</p>
<p>When the article is ready, add real image assets, descriptive internal links, and highlight the final keyword placements during review.</p>
<h2>Conclusion</h2>
<p>{keyword} articles work best when the structure is deliberate, the keyword placement is natural, and every section earns its place. Use this draft as a starting frame, then replace the placeholder facts with your actual brand proof, SERP findings, and internal links before publishing.</p>
<h2>FAQ</h2>
<h3>How many times should {keyword} appear in the article?</h3>
<p>Enough to stay natural. Priority placements are the title, H1, introduction, and conclusion.</p>
<h3>How long should a {keyword} article be?</h3>
<p>A practical target is around 1000-1500 words, but the final length should reflect the SERP and the depth of the topic.</p>
<h3>How can product information be added naturally?</h3>
<p>Use it as supporting proof, examples, or comparisons instead of forcing a hard-sell message into every section.</p>
""".strip()
        else:
            strategy = {
                "search_intent": "answer-seeking with AI citation potential",
                "audience": "readers who want a fast answer plus proof they can trust",
                "meta_title": truncate(f"{keyword} GEO Answer Template", int(rule_context["meta_title_limit"])),
                "meta_description": truncate(
                    f"Use this GEO-ready article structure for {keyword} with answer-first summaries, proof blocks, references, and FAQ sections.",
                    int(rule_context["meta_description_limit"]),
                ),
                "answer_first_summary": f"The short answer to {keyword} should appear immediately, followed by proof and references.",
                "entity_summary": brand_line,
                "h1_options": [f"{keyword}: A GEO-Ready Answer Page"],
                "outline": [
                    {"level": "H2", "title": "TL;DR"},
                    {"level": "H2", "title": f"The direct answer to {keyword}"},
                    {"level": "H2", "title": "Proof points and entity context"},
                    {"level": "H2", "title": "References and citation plan"},
                    {"level": "H2", "title": "Update log"},
                    {"level": "H2", "title": "Conclusion"},
                    {"level": "H2", "title": "FAQ"},
                ],
                "claim_blocks": [
                    {
                        "claim": f"A high-quality {keyword} answer should be visible in the opening section.",
                        "proof_hint": "Use concrete product or category evidence",
                        "citation_hint": "Reference benchmark studies, documentation, or policy pages",
                    }
                ],
                "faq_questions": [
                    f"What is the fastest answer to {keyword}?",
                    f"How should {keyword} be cited in AI search results?",
                    "What proof makes the article more trustworthy?",
                ],
                "reference_plan": [
                    "Manufacturer specifications, docs, or official product pages",
                    "Policy pages, benchmark reports, or research-backed explainers",
                ],
                "internal_link_plan": rule_context.get("resolved_internal_links", []),
                "compliance_notes": rule_context.get("required_notes", []),
                "schema_suggestions": ["Article", "FAQPage"],
                "trust_signals": ["author byline", "publish date", "last updated", "references", "TL;DR"],
                "image_briefs": [
                    f"Editorial hero image for {keyword}",
                    "Visual showing proof blocks and evidence structure",
                ],
            }
            html = f"""
<h1>{strategy["h1_options"][0]}</h1>
<h2>Quick Answer</h2>
<p>{strategy["answer_first_summary"]}</p>
<p>Readers who want the official version can review the {internal_link} before diving into the supporting explanation.</p>
<h2>The direct answer to {keyword}</h2>
<p>If the page is meant to perform in AI-driven discovery, the introduction should answer the core question first. Readers and systems alike should understand the conclusion without needing to scroll through a long setup section.</p>
<p>That opening answer should stay consistent with the rest of the page. If brand or product claims appear later, they should reinforce the same entity story instead of introducing a new angle halfway through the article.</p>
<h2>Proof points and entity context</h2>
<p>Strong GEO content is not just concise. It is also grounded. Add clear evidence types such as specs, benchmark data, official documentation, product details, or policy references whenever they strengthen a factual claim.</p>
<p><strong>Entity context:</strong> {brand_line}</p>
<ul>
  <li><strong>Answer-first:</strong> help systems extract the main takeaway quickly.</li>
  <li><strong>Proof blocks:</strong> pair claims with evidence hints and source categories.</li>
  <li><strong>Entity clarity:</strong> keep product names, descriptors, and positioning consistent.</li>
</ul>
<h2>References and citation plan</h2>
<p>Instead of inventing links, define the reference categories the final article should cite. Official product documentation, trusted third-party benchmarks, regulatory pages, and policy explainers are usually stronger than generic blog commentary.</p>
<p>This is also where inline citations, quote-ready facts, and clearly labeled updates can improve extraction quality.</p>
<h2>Update log</h2>
<p>Add visible freshness signals when the article is published. A publish date, a last-updated date, and a short note describing what changed can make the page easier to trust.</p>
<h2>Conclusion</h2>
<p>{keyword} pages work best when they are direct, evidence-backed, and consistent about the entities they discuss. Use this draft as the structure, then replace the placeholder proof guidance with verified citations before publishing.</p>
<h2>FAQ</h2>
<h3>What is the fastest answer to {keyword}?</h3>
<p>Give the short answer in the first screen, then expand with evidence and context.</p>
<h3>How should {keyword} be cited in AI search results?</h3>
<p>Use clear headings, compact paragraphs, and evidence-backed statements that can be quoted easily.</p>
<h3>What proof makes the article more trustworthy?</h3>
<p>Official specs, policy pages, benchmark data, and consistent entity descriptions usually help most.</p>
""".strip()

        return self._package_article(
            category=category,
            keyword=keyword,
            info=info,
            task_context=task_context,
            language=language,
            mode_type=normalized_mode_type,
            strategy=strategy,
            rule_context=rule_context,
            html=html,
            generation_mode="mock",
            word_limit=word_limit,
        )

    def _extract_outline_structure(self, outline_text: str) -> tuple[str, list[dict[str, str]]]:
        title = "Outline-based article"
        outline: list[dict[str, str]] = []

        for raw_line in outline_text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue

            markdown_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if markdown_match:
                level = len(markdown_match.group(1))
                heading = markdown_match.group(2).strip()
                if not heading:
                    continue
                if level == 1:
                    title = heading
                    continue
                outline.append({"level": "H2" if level == 2 else "H3", "title": heading})
                continue

            cleaned = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", raw_line).strip()
            cleaned = re.sub(r"^(H[23])[:：\-\s]+", "", cleaned, flags=re.IGNORECASE).strip()
            if not cleaned:
                continue

            indent = len(raw_line) - len(raw_line.lstrip())
            outline.append({"level": "H3" if indent >= 2 and outline else "H2", "title": cleaned})

        if title == "Outline-based article" and outline:
            title = outline[0]["title"]

        return title, outline

    def _attach_images(
        self,
        *,
        asset_namespace: str,
        article: dict[str, Any],
        category: str,
        keyword: str,
        mode_type: int,
        info: str,
        include_cover: int,
        content_image_count: int,
    ) -> dict[str, Any]:
        if not self.image_service:
            article["images"] = article.get("images") or []
            article["image_generation_mode"] = "disabled"
            return article

        article["raw_html"] = article.get("raw_html") or article.get("html", "")

        if int(include_cover) == 0 and int(content_image_count) == 0:
            article["images"] = article.get("images") or []
            article["image_generation_mode"] = "disabled"
            return article

        image_keyword = str(article.get("title") or keyword) if int(mode_type) == 2 else keyword
        assets = self.image_service.ensure_assets(
            asset_namespace=asset_namespace,
            category=category,
            keyword=image_keyword,
            info=info,
            article=article,
            include_cover=include_cover,
            content_image_count=content_image_count,
        )
        article["images"] = assets
        article["image_generation_mode"] = self.image_service.mode
        return article
