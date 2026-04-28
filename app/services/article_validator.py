from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


H1_RE = re.compile(r"<h1\b", re.IGNORECASE)
FIRST_H1_RE = re.compile(r"<h1\b[^>]*>.*?</h1>", re.IGNORECASE | re.DOTALL)
P_RE = re.compile(r"<p>(.*?)</p>", re.IGNORECASE | re.DOTALL)
FAQ_RE = re.compile(r"<h[23]>\s*FAQ\s*</h[23]>", re.IGNORECASE)
REFERENCES_RE = re.compile(r"<h[23]>\s*References?(?:\s+and\s+Evidence\s+to\s+Verify)?\s*</h[23]>", re.IGNORECASE)
CONCLUSION_RE = re.compile(r"<h2>\s*Conclusion\s*</h2>", re.IGNORECASE)
H2_SECTION_RE = re.compile(r"(<h2\b[^>]*>(.*?)</h2>)(.*?)(?=<h2\b|$)", re.IGNORECASE | re.DOTALL)


class ArticleValidator:
    def apply(
        self,
        article: dict[str, Any],
        *,
        category: str,
        keyword: str,
        rule_context: dict[str, Any],
    ) -> dict[str, Any]:
        working = deepcopy(article)
        html = str(working.get("raw_html") or working.get("html") or "")
        fixes: list[str] = []
        warnings: list[str] = []
        checks: list[dict[str, Any]] = []

        html, replacement_hits = self._replace_banned_terms(html, rule_context.get("banned_terms", {}))
        if replacement_hits:
            fixes.extend(replacement_hits)

        html, voice_hits = self._remove_third_party_voice(html)
        if voice_hits:
            fixes.extend(voice_hits)

        working["title"], title_trimmed = self._trim_text(
            str(working.get("title") or keyword),
            int(rule_context.get("meta_title_limit", 60)),
        )
        if title_trimmed:
            fixes.append("trimmed article title to the configured title limit")

        working["meta_title"], meta_title_trimmed = self._trim_text(
            str(working.get("meta_title") or working["title"]),
            int(rule_context.get("meta_title_limit", 60)),
        )
        if meta_title_trimmed:
            fixes.append("trimmed meta title to the configured title limit")

        working["meta_description"], meta_description_trimmed = self._trim_text(
            str(working.get("meta_description") or ""),
            int(rule_context.get("meta_description_limit", 160)),
        )
        if meta_description_trimmed:
            fixes.append("trimmed meta description to the configured description limit")

        html, quick_answer_added = self._ensure_quick_answer(
            html,
            keyword=keyword,
            summary=str((working.get("strategy") or {}).get("answer_first_summary") or ""),
            enabled=category == "geo",
        )
        if quick_answer_added:
            fixes.append("added a quick-answer block for GEO extraction")

        html, link_added = self._ensure_early_link(
            html,
            shopify_url=str(rule_context.get("shopify_url") or ""),
            requires_shopify_link=bool(rule_context.get("requires_shopify_link", False)),
        )
        if link_added:
            fixes.append("added an early internal product link")

        html, disclaimer_added = self._ensure_disclaimer(
            html,
            disclaimer=str(rule_context.get("required_disclaimer") or ""),
            category=category,
        )
        if disclaimer_added:
            fixes.append("added the required disclaimer block")

        html, references_added = self._ensure_references(
            html,
            enabled=category == "geo",
            links=rule_context.get("resolved_internal_links") or [],
            notes=rule_context.get("required_notes") or [],
        )
        if references_added:
            fixes.append("added a references and verification section")

        if category == "geo":
            html, geo_fix_notes = self._normalize_geo_structure(
                html,
                keyword=keyword,
                summary=str((working.get("strategy") or {}).get("answer_first_summary") or ""),
                disclaimer=str(rule_context.get("required_disclaimer") or ""),
            )
            fixes.extend(geo_fix_notes)

        html, density_fix_notes = self._normalize_body_density(
            html,
            category=category,
            word_limit=int(working.get("word_limit") or 1200),
        )
        fixes.extend(density_fix_notes)

        h1_count = len(H1_RE.findall(html))
        if h1_count != 1:
            warnings.append(f"expected exactly one H1, found {h1_count}")
        checks.append({"name": "single_h1", "passed": h1_count == 1, "detail": f"H1 count: {h1_count}"})

        disclaimer_required = bool(rule_context.get("required_disclaimer"))
        disclaimer_present = not disclaimer_required or "Disclaimer" in html
        checks.append(
            {
                "name": "required_disclaimer",
                "passed": disclaimer_present,
                "detail": "present" if disclaimer_present else "missing",
            }
        )
        if disclaimer_required and not disclaimer_present:
            warnings.append("required disclaimer is still missing after remediation")

        if category == "geo":
            quick_answer_present = "Quick Answer" in html
            references_present = bool(REFERENCES_RE.search(html))
            faq_present = bool(FAQ_RE.search(html))
            conclusion_present = bool(CONCLUSION_RE.search(html))
            structure_order_ok = self._geo_structure_order_is_valid(html)
            checks.append(
                {
                    "name": "geo_structure",
                    "passed": quick_answer_present and references_present and faq_present and conclusion_present and structure_order_ok,
                    "detail": (
                        f"quick_answer={quick_answer_present}, references={references_present}, faq={faq_present}, "
                        f"conclusion={conclusion_present}, ordered={structure_order_ok}"
                    ),
                }
            )
            if not (quick_answer_present and references_present and faq_present and conclusion_present and structure_order_ok):
                warnings.append("GEO structure is missing or out of order for Quick Answer, References, FAQ, or Conclusion")

        early_link_required = bool(rule_context.get("requires_shopify_link") and rule_context.get("shopify_url"))
        early_link_present = not early_link_required or self._has_early_link(
            html,
            url=str(rule_context.get("shopify_url") or ""),
        )
        checks.append(
            {
                "name": "early_internal_link",
                "passed": early_link_present,
                "detail": "present" if early_link_present else "missing",
            }
        )
        if not early_link_present:
            warnings.append("required early internal link is missing")

        score = max(0, 100 - len(warnings) * 15)
        working["raw_html"] = html.strip()
        working["html"] = working["raw_html"]
        working["audit"] = {
            "score": score,
            "warnings": warnings,
            "applied_fixes": fixes,
            "checks": checks,
            "applied_rule_ids": rule_context.get("applied_rule_ids", []),
            "resolved_internal_links": rule_context.get("resolved_internal_links", []),
            "context": rule_context.get("context", {}),
        }
        return working

    def _replace_banned_terms(self, html: str, banned_terms: dict[str, str]) -> tuple[str, list[str]]:
        fixes: list[str] = []
        updated = html
        for source, replacement in banned_terms.items():
            pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
            if not pattern.search(updated):
                continue
            updated = pattern.sub(replacement, updated)
            fixes.append(f"replaced banned term '{source}'")
        return updated, fixes

    def _trim_text(self, value: str, limit: int) -> tuple[str, bool]:
        text = value.strip()
        if len(text) <= limit:
            return text, False
        return text[: limit - 3].rstrip() + "...", True

    def _ensure_quick_answer(self, html: str, *, keyword: str, summary: str, enabled: bool) -> tuple[str, bool]:
        if not enabled:
            return html, False
        if "Quick Answer" in html:
            return html, False
        h1_match = FIRST_H1_RE.search(html)
        block = self._quick_answer_block(keyword, summary)
        if not h1_match:
            return f"{block}\n{html}", True
        insertion_point = h1_match.end()
        return html[:insertion_point] + "\n" + block + html[insertion_point:], True

    def _ensure_early_link(self, html: str, *, shopify_url: str, requires_shopify_link: bool) -> tuple[str, bool]:
        if not requires_shopify_link or not shopify_url:
            return html, False
        if self._has_early_link(html, shopify_url):
            return html, False
        paragraphs = list(P_RE.finditer(html))
        if not paragraphs:
            return html, False
        first = paragraphs[0]
        snippet = (
            f'{first.group(0)}<p>For product-specific details, see the official <a href="{shopify_url}">product page</a>.</p>'
        )
        return html[: first.start()] + snippet + html[first.end() :], True

    def _ensure_disclaimer(self, html: str, *, disclaimer: str, category: str) -> tuple[str, bool]:
        if not disclaimer:
            return html, False
        if disclaimer in html or "Disclaimer" in html:
            return html, False
        if category == "geo":
            conclusion_match = CONCLUSION_RE.search(html)
            block = f'<p><strong>Disclaimer:</strong> {disclaimer}</p>'
            if conclusion_match:
                insert_at = conclusion_match.end()
                return html[:insert_at] + block + html[insert_at:], True
            return f"{html}\n{block}", True
        block = f"<h2>Disclaimer</h2><p>{disclaimer}</p>"
        faq_match = FAQ_RE.search(html)
        if faq_match:
            return html[: faq_match.start()] + block + html[faq_match.start() :], True
        return f"{html}\n{block}", True

    def _ensure_references(
        self,
        html: str,
        *,
        enabled: bool,
        links: list[dict[str, str]],
        notes: list[str],
    ) -> tuple[str, bool]:
        if not enabled:
            return html, False
        if REFERENCES_RE.search(html):
            return html, False
        items = [
            "<li>Verify all product claims against official specifications before publishing.</li>",
            "<li>Support policy or utility claims with official program or government sources.</li>",
        ]
        for link in links[:3]:
            items.append(f'<li>Internal reference: <a href="{link["url"]}">{link["label"]}</a>.</li>')
        for note in notes[:2]:
            items.append(f"<li>{note}</li>")
        block = "<h2>References and Evidence to Verify</h2><ul>" + "".join(items) + "</ul>"
        faq_match = FAQ_RE.search(html)
        if faq_match:
            return html[: faq_match.start()] + block + html[faq_match.start() :], True
        return f"{html}\n{block}", True

    def _has_early_link(self, html: str, url: str) -> bool:
        paragraphs = list(P_RE.finditer(html))[:2]
        return any(url in match.group(0) for match in paragraphs)

    def _remove_third_party_voice(self, html: str) -> tuple[str, list[str]]:
        replacements = [
            (r"(?i)\bAccording to official docs,?\s*", ""),
            (r"(?i)\bAccording to the official documentation,?\s*", ""),
            (r"(?i)\bBased on official documentation,?\s*", ""),
            (r"(?i)\bBased on the official documentation,?\s*", ""),
            (r"(?i)\bThrough official documentation we can conclude that\s*", ""),
            (r"(?i)\bThrough the official documentation,? we can conclude that\s*", ""),
            (r"通过官方文档可以得出[:：]?\s*", ""),
            (r"根据官方文档可以得出[:：]?\s*", ""),
        ]
        updated = html
        fixes: list[str] = []
        for pattern, replacement in replacements:
            next_html, count = re.subn(pattern, replacement, updated)
            if count:
                updated = next_html
                fixes.append(f"removed third-party narrator phrasing matching '{pattern}'")
        return updated, fixes

    def _normalize_geo_structure(
        self,
        html: str,
        *,
        keyword: str,
        summary: str,
        disclaimer: str,
    ) -> tuple[str, list[str]]:
        h1_match = FIRST_H1_RE.search(html)
        if not h1_match:
            return html, []

        h1_block = h1_match.group(0).strip()
        remainder = html[h1_match.end() :]
        first_h2_match = re.search(r"<h2\b", remainder, re.IGNORECASE)
        preamble = remainder[: first_h2_match.start()] if first_h2_match else remainder
        section_source = remainder[first_h2_match.start() :] if first_h2_match else ""

        quick_content = ""
        references_content = ""
        faq_content = ""
        conclusion_content = ""
        body_sections: list[str] = []
        fixes: list[str] = []

        for match in H2_SECTION_RE.finditer(section_source):
            heading_html = match.group(1)
            heading_text = self._strip_tags(match.group(2)).strip()
            content = match.group(3).strip()
            heading_key = re.sub(r"\s+", " ", heading_text.lower())

            if heading_key == "quick answer" or heading_key == "tl;dr":
                if not quick_content:
                    quick_content = content
                fixes.append("normalized the GEO quick-answer section heading")
                continue
            if heading_key in {"faq", "update log", "appendix"}:
                if heading_key == "faq":
                    if not faq_content:
                        faq_content = content
                    fixes.append("normalized the GEO FAQ section heading")
                else:
                    fixes.append(f"removed unsupported GEO section '{heading_text}'")
                continue
            if "reference" in heading_key or "citation" in heading_key or "evidence to verify" in heading_key:
                if not references_content:
                    references_content = content
                fixes.append("normalized the GEO references section heading")
                continue
            if heading_key == "conclusion":
                if not conclusion_content:
                    conclusion_content = content
                fixes.append("normalized the GEO conclusion section heading")
                continue

            body_sections.append(f"{heading_html}{content}")

        if not quick_content:
            quick_content = preamble.strip()
        if not quick_content:
            quick_content = f"<p>{self._quick_answer_text(keyword, summary)}</p>"
            fixes.append("added fallback quick-answer content for GEO structure")

        if not references_content:
            references_content = (
                "<ul>"
                "<li>Verify product and policy claims against official source materials before publishing.</li>"
                "<li>Use the cited AI Q&A sources only when they are actually supported by the final article.</li>"
                "</ul>"
            )
            fixes.append("added fallback references content for GEO structure")

        if not faq_content or not re.search(r"<h3\b", faq_content, re.IGNORECASE):
            faq_content = self._build_geo_faq_content(keyword)
            fixes.append("added fallback GEO FAQ content")

        if not body_sections:
            body_sections.append(
                f"<h2>Key Details About {keyword}</h2>"
                "<p>Expand the main answer with verifiable details, decision criteria, and entity-specific facts.</p>"
            )
            fixes.append("added a fallback GEO body section")

        if not conclusion_content:
            conclusion_text = (
                f"{keyword} works best as GEO content when the page gives the answer first, supports it with verifiable details, "
                "and closes with a concise takeaway."
            )
            conclusion_content = f"<p>{conclusion_text}</p>"
            fixes.append("added fallback GEO conclusion content")

        if disclaimer and disclaimer not in conclusion_content and "Disclaimer" not in conclusion_content:
            conclusion_content = f'<p><strong>Disclaimer:</strong> {disclaimer}</p>{conclusion_content}'
            fixes.append("moved disclaimer into the GEO conclusion section")

        quick_wrapped = self._ensure_wrapped_html(quick_content)
        quick_inline = self._make_inline_quick_answer(quick_wrapped)
        rebuilt = [
            h1_block,
            quick_inline,
            *[section.strip() for section in body_sections],
            f"<h2>References and Evidence to Verify</h2>{self._ensure_wrapped_html(references_content)}",
            f"<h2>FAQ</h2>{self._ensure_wrapped_html(faq_content)}",
            f"<h2>Conclusion</h2>{self._ensure_wrapped_html(conclusion_content)}",
        ]
        return "\n".join(part for part in rebuilt if part).strip(), fixes

    def _geo_structure_order_is_valid(self, html: str) -> bool:
        h1_match = FIRST_H1_RE.search(html)
        quick_match = re.search(r"<strong>\s*Quick Answer\s*[:：]?\s*</strong>", html, re.IGNORECASE)
        references_match = REFERENCES_RE.search(html)
        faq_match = FAQ_RE.search(html)
        conclusion_match = CONCLUSION_RE.search(html)
        if not (h1_match and quick_match and references_match and faq_match and conclusion_match):
            return False
        if not (h1_match.start() < quick_match.start() < references_match.start() < faq_match.start() < conclusion_match.start()):
            return False
        tail = html[conclusion_match.end() :].strip()
        return "<h2" not in tail.lower()

    def _quick_answer_block(self, keyword: str, summary: str) -> str:
        text = self._quick_answer_text(keyword, summary)
        return f"<p><strong>Quick Answer:</strong> {text}</p>"

    def _quick_answer_text(self, keyword: str, summary: str) -> str:
        return summary.strip() or (
            f"The short answer is that {keyword} content works best when it provides a direct recommendation first, "
            "then backs it up with verifiable product details, links, and source guidance."
        )

    def _make_inline_quick_answer(self, wrapped_html: str) -> str:
        """Ensure the quick-answer content starts with <strong>Quick Answer:</strong> inline."""
        if "Quick Answer" in wrapped_html:
            return wrapped_html
        p_match = re.match(r"<p>(.*)", wrapped_html, re.IGNORECASE | re.DOTALL)
        if p_match:
            return f"<p><strong>Quick Answer:</strong> {p_match.group(1)}"
        return f"<p><strong>Quick Answer:</strong> {wrapped_html}</p>"

    def _first_paragraph_text(self, html: str) -> str:
        match = P_RE.search(html)
        return re.sub(r"<[^>]+>", " ", match.group(1)).strip() if match else ""

    def _strip_tags(self, value: str) -> str:
        return re.sub(r"<[^>]+>", " ", value)

    def _ensure_wrapped_html(self, value: str) -> str:
        content = value.strip()
        if not content:
            return ""
        if re.match(r"^<(p|ul|ol|h3)\b", content, re.IGNORECASE):
            return content
        return f"<p>{content}</p>"

    def _build_geo_faq_content(self, keyword: str) -> str:
        questions = [
            (
                f"What should I check first about {keyword}?",
                f"Start with the direct answer, then verify the main product, policy, or comparison details that affect {keyword} in real use.",
            ),
            (
                f"How can I tell whether {keyword} is the right fit for my situation?",
                "Compare the decision criteria that matter most in practice, such as compatibility, limits, setup effort, or ongoing cost.",
            ),
        ]
        return "".join(f"<h3>{question}</h3><p>{answer}</p>" for question, answer in questions)

    def _normalize_body_density(self, html: str, *, category: str, word_limit: int) -> tuple[str, list[str]]:
        h1_match = FIRST_H1_RE.search(html)
        if not h1_match:
            return html, []

        remainder = html[h1_match.end() :]
        first_h2_match = re.search(r"<h2\b", remainder, re.IGNORECASE)
        if not first_h2_match:
            return html, []

        limits = self._density_limits(word_limit)
        h1_block = h1_match.group(0).strip()
        preamble = remainder[: first_h2_match.start()]
        section_source = remainder[first_h2_match.start() :]
        special_titles = self._special_h2_titles(category)

        body_sections: list[dict[str, str]] = []
        special_sections: list[str] = []
        fixes: list[str] = []

        for match in H2_SECTION_RE.finditer(section_source):
            heading_html = match.group(1)
            heading_text = self._strip_tags(match.group(2)).strip()
            content = match.group(3).strip()
            heading_key = re.sub(r"\s+", " ", heading_text.lower())
            full_section = f"{heading_html}{content}"
            if heading_key in special_titles:
                special_sections.append(full_section)
                continue
            body_sections.append({"heading_html": heading_html, "title": heading_text, "content": content})

        if not body_sections:
            return html, []

        condensed_sections: list[dict[str, str]] = []
        for section in body_sections:
            if condensed_sections and self._count_content_blocks(section["content"]) < 2:
                condensed_sections[-1]["content"] += self._render_subsection(section["title"], section["content"])
                fixes.append(f"merged a short body H2 section '{section['title']}' into the previous section")
                continue
            condensed_sections.append(section)

        while len(condensed_sections) > limits["max_h2"] and len(condensed_sections) > 1:
            extra = condensed_sections.pop()
            condensed_sections[-1]["content"] += self._render_subsection(extra["title"], extra["content"])
            fixes.append(f"collapsed an extra body H2 section '{extra['title']}' into the previous section")

        remaining_h3 = limits["max_h3"]
        for section in condensed_sections:
            normalized_content, remaining_h3, converted = self._limit_h3_usage(section["content"], remaining_h3)
            if converted:
                fixes.append(f"reduced H3 density inside '{section['title']}'")
            section["content"] = normalized_content

        rebuilt = [
            h1_block,
            preamble.strip(),
            *[f"{section['heading_html']}{section['content']}".strip() for section in condensed_sections],
            *[section.strip() for section in special_sections],
        ]
        return "\n".join(part for part in rebuilt if part).strip(), fixes

    def _density_limits(self, word_limit: int) -> dict[str, int]:
        normalized_limit = max(200, int(word_limit))
        if normalized_limit <= 1000:
            return {"max_h2": 2, "max_h3": 2}
        if normalized_limit <= 1400:
            return {"max_h2": 3, "max_h3": 3}
        if normalized_limit <= 1800:
            return {"max_h2": 4, "max_h3": 4}
        return {"max_h2": 5, "max_h3": 5}

    def _special_h2_titles(self, category: str) -> set[str]:
        if category == "geo":
            return {"references and evidence to verify", "faq", "conclusion"}
        return {"conclusion", "faq", "disclaimer"}

    def _count_content_blocks(self, content: str) -> int:
        return len(re.findall(r"<(p|ul|ol|h3)\b", content, re.IGNORECASE))

    def _render_subsection(self, title: str, content: str) -> str:
        body = content.strip() or "<p>Expand this supporting point with concrete detail.</p>"
        return f"<h3>{title}</h3>{body}"

    def _limit_h3_usage(self, content: str, remaining_h3: int) -> tuple[str, int, bool]:
        pattern = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.IGNORECASE | re.DOTALL)
        parts: list[str] = []
        last_end = 0
        converted = False

        for match in pattern.finditer(content):
            parts.append(content[last_end : match.start()])
            title = self._strip_tags(match.group(1)).strip()
            if remaining_h3 > 0:
                parts.append(match.group(0))
                remaining_h3 -= 1
            else:
                parts.append(f"<p><strong>{title}:</strong></p>")
                converted = True
            last_end = match.end()

        parts.append(content[last_end:])
        return "".join(parts), remaining_h3, converted
