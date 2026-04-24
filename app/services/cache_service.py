from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.task_modes import normalize_mode_type
from app.utils.common import canonical_json, ensure_dir, load_json, normalize_text


def _coerce_mode_and_context(
    mode_type: int | dict[str, Any],
    task_context: dict[str, Any] | None,
) -> tuple[int, dict[str, Any] | None]:
    if isinstance(mode_type, dict):
        return 1, mode_type if task_context is None else task_context
    return normalize_mode_type(mode_type), task_context


class CacheService:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        ensure_dir(cache_dir)

    def build_key(
        self,
        category: str,
        keyword: str,
        info: str,
        mode_type: int = 1,
        task_context: dict[str, Any] | None = None,
        word_limit: int = 1200,
        access_tier: str = "standard",
        provider: str = "openai",
    ) -> str:
        normalized_mode_type, normalized_task_context = _coerce_mode_and_context(mode_type, task_context)
        raw = "||".join(
            [
                normalize_text(category),
                normalize_text(keyword),
                str(normalized_mode_type),
                normalize_text(info),
                canonical_json(normalized_task_context or {}),
                str(max(200, int(word_limit))),
                normalize_text(access_tier or "standard"),
                normalize_text(provider or "openai"),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        category: str,
        keyword: str,
        info: str,
        mode_type: int = 1,
        task_context: dict[str, Any] | None = None,
        word_limit: int = 1200,
        access_tier: str = "standard",
        provider: str = "openai",
    ) -> dict[str, Any] | None:
        normalized_mode_type, normalized_task_context = _coerce_mode_and_context(mode_type, task_context)
        path = self.path_for(
            category,
            keyword,
            info,
            normalized_mode_type,
            normalized_task_context,
            word_limit,
            access_tier,
            provider,
        )
        if not path.exists():
            return None
        return load_json(path)

    def set(
        self,
        category: str,
        keyword: str,
        info: str,
        article: dict[str, Any],
        mode_type: int = 1,
        task_context: dict[str, Any] | None = None,
        word_limit: int = 1200,
        access_tier: str = "standard",
        provider: str = "openai",
    ) -> dict[str, Any]:
        normalized_mode_type, normalized_task_context = _coerce_mode_and_context(mode_type, task_context)
        payload = {
            "key": self.build_key(
                category,
                keyword,
                info,
                normalized_mode_type,
                normalized_task_context,
                word_limit,
                access_tier,
                provider,
            ),
            "category": category,
            "keyword": keyword,
            "mode_type": normalized_mode_type,
            "info": info,
            "task_context": normalized_task_context or {},
            "word_limit": int(word_limit),
            "access_tier": access_tier or "standard",
            "provider": provider or "openai",
            "article": article,
        }
        path = self.path_for(
            category,
            keyword,
            info,
            normalized_mode_type,
            normalized_task_context,
            word_limit,
            access_tier,
            provider,
        )
        ensure_dir(path.parent)
        path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def path_for(
        self,
        category: str,
        keyword: str,
        info: str,
        mode_type: int = 1,
        task_context: dict[str, Any] | None = None,
        word_limit: int = 1200,
        access_tier: str = "standard",
        provider: str = "openai",
    ) -> Path:
        normalized_mode_type, normalized_task_context = _coerce_mode_and_context(mode_type, task_context)
        return self.cache_dir / (
            f"{self.build_key(category, keyword, info, normalized_mode_type, normalized_task_context, word_limit, access_tier, provider)}.json"
        )
