from __future__ import annotations

from typing import Any

from .llm_client import LLMClient
from .prompt_builder import (
    build_draft_prompt,
    build_polish_prompt,
    build_strategy_prompt,
)
from .utils import extract_json_object, slugify, truncate


class WriterService:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def generate(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        language: str = "English",
    ) -> dict[str, Any]:
        if self.llm_client.enabled:
            strategy_prompt = build_strategy_prompt(category, keyword, info, language)
            raw_strategy = self.llm_client.complete(strategy_prompt, expect_json=True)
            strategy = extract_json_object(raw_strategy)

            draft_prompt = build_draft_prompt(category, keyword, info, language, strategy)
            draft_html = self.llm_client.complete(draft_prompt)

            polish_prompt = build_polish_prompt(category, language, keyword, draft_html)
            polished_html = self.llm_client.complete(polish_prompt)

            return self._package_article(
                category=category,
                keyword=keyword,
                info=info,
                language=language,
                strategy=strategy,
                html=polished_html.strip(),
                generation_mode="llm",
            )

        return self._mock_article(
            category=category,
            keyword=keyword,
            info=info,
            language=language,
        )

    def _package_article(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        language: str,
        strategy: dict[str, Any],
        html: str,
        generation_mode: str,
    ) -> dict[str, Any]:
        title = (
            (strategy.get("h1_options") or [keyword])[0]
            if isinstance(strategy.get("h1_options"), list)
            else keyword
        )
        return {
            "category": category,
            "keyword": keyword,
            "language": language,
            "title": title,
            "meta_title": truncate(strategy.get("meta_title") or title, 60),
            "meta_description": truncate(
                strategy.get("meta_description")
                or f"{keyword} article for {info or 'your brand'}",
                160,
            ),
            "slug": slugify(title),
            "html": html,
            "strategy": strategy,
            "generation_mode": generation_mode,
        }

    def _mock_article(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        language: str,
    ) -> dict[str, Any]:
        brand_line = info.strip() or "Use your real brand, product facts, and proof here."

        if category == "seo":
            strategy = {
                "intent": "informational with commercial support",
                "audience": "buyers researching the topic before making a decision",
                "meta_title": truncate(f"{keyword} Guide for Better Rankings", 60),
                "meta_description": truncate(
                    f"Learn how to write about {keyword} with a clear SEO structure, natural keyword placement, and a stronger conversion path.",
                    160,
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
            }
            html = f"""
<h1>{strategy["h1_options"][0]}</h1>
<p>{keyword} content performs best when it solves the reader's question immediately, keeps the structure clean, and uses product context only where it adds real value. This demo article is a scaffold, but it already follows the same three-step idea from your PHP flow: strategy first, drafting second, polishing third.</p>
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
                "meta_title": truncate(f"{keyword} GEO Answer Template", 60),
                "meta_description": truncate(
                    f"Use this GEO-ready article structure for {keyword} with answer-first summaries, proof blocks, references, and FAQ sections.",
                    160,
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
                        "claim": f"{keyword} needs an answer-first article format.",
                        "proof_hint": "Use product specs, policy pages, benchmarks, or expert docs.",
                        "citation_hint": "Prefer official documentation or first-party evidence.",
                    }
                ],
                "faq_questions": [
                    f"What makes a {keyword} page easy for AI systems to quote?",
                    f"How should references be added to a {keyword} article?",
                    "What trust signals should appear on the page?",
                ],
                "reference_plan": [
                    "Official documentation",
                    "Product specification sheet",
                    "Support knowledge base",
                ],
                "schema_suggestions": ["Article", "FAQPage", "Organization"],
                "trust_signals": ["author byline", "publish date", "last updated", "references", "TL;DR"],
            }
            html = f"""
<h1>{strategy["h1_options"][0]}</h1>
<p><strong>TL;DR:</strong> The best {keyword} page gives the answer early, backs it with proof, and makes the entity behind the answer easy to verify. That structure is what helps AI systems quote, summarize, and trust the page instead of treating it like generic marketing copy.</p>
<h2>The direct answer to {keyword}</h2>
<p>If you want a page to perform in GEO scenarios, the first screen should resolve the user question directly. The article should not hide the main answer behind a long setup. Instead, it should move quickly from answer to proof.</p>
<p>This is especially important when a reader may encounter your content through AI summaries rather than through a traditional ten-blue-links search flow.</p>
<h2>Proof points and entity context</h2>
<p>Every important claim should point to a proof source, a measurable detail, or a clearly attributable internal fact. Strong GEO pages are easier to cite because their statements are easier to verify.</p>
<ul>
  <li><strong>Entity summary:</strong> {brand_line}</li>
  <li><strong>Proof block:</strong> add benchmarks, specs, policy references, or support documentation.</li>
  <li><strong>Trust signals:</strong> include author, publish date, and last updated information.</li>
</ul>
<h2>References and citation plan</h2>
<p>Do not rely on vague authority language. A GEO-ready page should expose where the information comes from, what type of source supports it, and which statements deserve inline citations.</p>
<p>Recommended reference types for this draft include official documentation, product specification sheets, knowledge-base articles, third-party benchmarks, and expert commentary when appropriate.</p>
<h2>Update log</h2>
<p>Add a visible update note whenever product specs, policies, or feature details change. Freshness helps both human readers and machine systems understand whether the page is still safe to quote.</p>
<h2>Conclusion</h2>
<p>{keyword} content works better in GEO when it feels answerable, attributable, and trustworthy. Before publishing, replace the placeholders in this draft with real evidence, descriptive internal links, and consistent brand entity data.</p>
<h2>FAQ</h2>
<h3>What makes a {keyword} page easy for AI systems to quote?</h3>
<p>Direct answers, structured headings, proof-based claims, and visible references make extraction easier.</p>
<h3>How should references be added to a {keyword} article?</h3>
<p>Use a references section plus inline citation cues around factual claims, comparisons, and statistics.</p>
<h3>What trust signals should appear on the page?</h3>
<p>At minimum, show the author, publish or update date, entity context, and the source type behind important claims.</p>
""".strip()

        return self._package_article(
            category=category,
            keyword=keyword,
            info=info,
            language=language,
            strategy=strategy,
            html=html,
            generation_mode="mock",
        )

