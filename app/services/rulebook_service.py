from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.utils.common import normalize_text


RULEBOOK_PATH = Path(__file__).resolve().parents[1] / "data" / "rulebook.json"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = item.strip()
        if not text:
            continue
        key = normalize_text(text)
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


class RulebookService:
    def __init__(self, rulebook_path: Path | None = None) -> None:
        self.rulebook_path = rulebook_path or RULEBOOK_PATH
        self.rulebook = self._load_rulebook()

    def _load_rulebook(self) -> dict[str, Any]:
        return json.loads(self.rulebook_path.read_text(encoding="utf-8"))

    def normalize_task_context(self, task_context: dict[str, Any] | None) -> dict[str, Any]:
        context = deepcopy(task_context or {})
        normalized = {
            "country": normalize_text(str(context.get("country") or "")),
            "market": normalize_text(str(context.get("market") or "")),
            "locale_variant": str(context.get("locale_variant") or "").strip(),
            "article_type": normalize_text(str(context.get("article_type") or "")),
            "product_line": normalize_text(str(context.get("product_line") or "")),
            "topic_flags": _dedupe([str(item) for item in context.get("topic_flags") or []]),
            "mentions_other_brands": bool(context.get("mentions_other_brands", False)),
            "requires_shopify_link": bool(context.get("requires_shopify_link", False)),
            "shopify_url": str(context.get("shopify_url") or "").strip(),
            "ai_qa_content": str(context.get("ai_qa_content") or "").strip(),
            "ai_qa_source": str(context.get("ai_qa_source") or "").strip(),
            "internal_links": [
                {
                    "label": str(item.get("label") or "").strip(),
                    "url": str(item.get("url") or "").strip(),
                }
                for item in context.get("internal_links") or []
                if str(item.get("label") or "").strip() and str(item.get("url") or "").strip()
            ],
        }
        if not normalized["market"] and normalized["country"]:
            country_rule = self.rulebook.get("country_rules", {}).get(normalized["country"], {})
            normalized["market"] = normalize_text(str(country_rule.get("market") or ""))
        if not normalized["locale_variant"] and normalized["country"]:
            country_rule = self.rulebook.get("country_rules", {}).get(normalized["country"], {})
            normalized["locale_variant"] = str(country_rule.get("locale_variant") or "").strip()
        if normalized["mentions_other_brands"] and normalized["article_type"] != "competitor_comparison":
            normalized["topic_flags"] = _dedupe(normalized["topic_flags"] + ["competitor_comparison"])
        if normalized["article_type"]:
            normalized["topic_flags"] = _dedupe(normalized["topic_flags"] + [normalized["article_type"]])
        return normalized

    def resolve_rules(
        self,
        *,
        category: str,
        language: str,
        task_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = self.normalize_task_context(task_context)
        category_key = normalize_text(category)
        language_text = str(language or "English").strip() or "English"
        global_rules = deepcopy(self.rulebook.get("global", {}))
        category_rules = deepcopy(self.rulebook.get("category_rules", {}).get(category_key, {}))
        market_rules = deepcopy(self.rulebook.get("market_rules", {}).get(context.get("market") or "", {}))
        country_rules = deepcopy(self.rulebook.get("country_rules", {}).get(context.get("country") or "", {}))
        article_type_rules = deepcopy(
            self.rulebook.get("article_type_rules", {}).get(context.get("article_type") or "", {})
        )
        product_rules = deepcopy(self.rulebook.get("product_rules", {}).get(context.get("product_line") or "", {}))
        country_override = deepcopy(
            product_rules.get("country_overrides", {}).get(context.get("country") or "", {})
        )

        resolved_internal_links = _dedupe_links(
            [*country_rules.get("internal_link_targets", []), *context.get("internal_links", [])]
        )
        required_disclaimer = (
            str(article_type_rules.get("required_disclaimer") or country_override.get("required_disclaimer") or "").strip()
            or None
        )
        required_notes = _dedupe(
            [
                *category_rules.get("notes", []),
                *market_rules.get("notes", []),
                *article_type_rules.get("notes", []),
                *product_rules.get("notes", []),
                *([product_rules.get("required_note")] if product_rules.get("required_note") else []),
                *([country_override.get("required_note")] if country_override.get("required_note") else []),
            ]
        )

        applied_rule_ids = _dedupe(
            [
                f"category:{category_key}",
                *(["market:" + context["market"]] if context.get("market") else []),
                *(["country:" + context["country"]] if context.get("country") else []),
                *(["article_type:" + context["article_type"]] if context.get("article_type") else []),
                *(["product:" + context["product_line"]] if context.get("product_line") else []),
            ]
        )

        return {
            "category": category_key,
            "language": language_text,
            "context": context,
            "applied_rule_ids": applied_rule_ids,
            "meta_title_limit": int(global_rules.get("meta_title_limit", 60)),
            "meta_description_limit": int(global_rules.get("meta_description_limit", 160)),
            "banned_terms": global_rules.get("banned_terms", {}),
            "writing_goals": category_rules.get("writing_goals", []),
            "required_sections": category_rules.get("required_sections", []),
            "required_disclaimer": required_disclaimer,
            "required_notes": required_notes,
            "resolved_internal_links": resolved_internal_links,
            "requires_shopify_link": bool(
                context.get("requires_shopify_link") or market_rules.get("requires_shopify_link", False)
            ),
            "shopify_url": context.get("shopify_url", ""),
            "locale_variant": context.get("locale_variant") or language_text,
            "market_flags": {
                "early_product_placement": bool(market_rules.get("early_product_placement", False)),
                "avoid_year_in_title": bool(market_rules.get("avoid_year_in_title", False)),
                "use_static_product_links": bool(market_rules.get("use_static_product_links", False)),
            },
            "product_priority": product_rules.get("priority"),
            "image_notes": _dedupe([*product_rules.get("image_notes", []), *country_override.get("image_notes", [])]),
        }


def _dedupe_links(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in items:
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        if not label or not url:
            continue
        key = (normalize_text(label), url)
        if key in seen:
            continue
        seen.add(key)
        result.append({"label": label, "url": url})
    return result
