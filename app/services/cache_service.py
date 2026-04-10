from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.utils.common import ensure_dir, load_json, normalize_text


class CacheService:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        ensure_dir(cache_dir)

    def build_key(self, category: str, keyword: str, info: str, word_limit: int = 1200) -> str:
        raw = "||".join(
            [
                normalize_text(category),
                normalize_text(keyword),
                normalize_text(info),
                str(max(200, int(word_limit))),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, category: str, keyword: str, info: str, word_limit: int = 1200) -> dict[str, Any] | None:
        path = self.path_for(category, keyword, info, word_limit)
        if not path.exists():
            return None
        return load_json(path)

    def set(
        self,
        category: str,
        keyword: str,
        info: str,
        article: dict[str, Any],
        word_limit: int = 1200,
    ) -> dict[str, Any]:
        payload = {
            "key": self.build_key(category, keyword, info, word_limit),
            "category": category,
            "keyword": keyword,
            "info": info,
            "word_limit": int(word_limit),
            "article": article,
        }
        path = self.path_for(category, keyword, info, word_limit)
        ensure_dir(path.parent)
        path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def path_for(self, category: str, keyword: str, info: str, word_limit: int = 1200) -> Path:
        return self.cache_dir / f"{self.build_key(category, keyword, info, word_limit)}.json"
