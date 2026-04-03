from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Lock
from typing import Any

from .utils import atomic_write_json, ensure_dir, load_json, normalize_text, utcnow_iso


class CacheService:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self._lock = Lock()
        ensure_dir(cache_dir)

    def build_key(self, category: str, keyword: str, info: str) -> str:
        payload = "\n".join(
            [category.strip().lower(), normalize_text(keyword), normalize_text(info)]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, category: str, keyword: str, info: str) -> dict[str, Any] | None:
        key = self.build_key(category, keyword, info)
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        return load_json(path)

    def set(
        self,
        category: str,
        keyword: str,
        info: str,
        article: dict[str, Any],
    ) -> dict[str, Any]:
        key = self.build_key(category, keyword, info)
        payload = {
            "cache_key": key,
            "category": category,
            "keyword": keyword,
            "info": info,
            "created_at": utcnow_iso(),
            "article": article,
        }
        path = self.cache_dir / f"{key}.json"
        with self._lock:
            atomic_write_json(path, payload)
        return payload

