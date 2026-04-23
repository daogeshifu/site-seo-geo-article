from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    return cleaned


def slugify(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff\s-]", "", value)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "article"


def seo_slugify(value: str, max_length: int = 75, max_segments: int = 10) -> str:
    slug = slugify(value)
    if not slug:
        return "article"

    parts = [part for part in slug.split("-") if part][: max(1, int(max_segments))]
    candidate = "-".join(parts).strip("-") or "article"
    if len(candidate) <= max_length:
        return candidate

    trimmed_parts: list[str] = []
    current_length = 0
    for part in parts:
        extra = len(part) if not trimmed_parts else len(part) + 1
        if current_length + extra > max_length:
            break
        trimmed_parts.append(part)
        current_length += extra

    if trimmed_parts:
        return "-".join(trimmed_parts).strip("-") or "article"

    return candidate[:max_length].rstrip("-") or "article"


def truncate(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def split_keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        text = str(value or "")
        raw_items = re.split(r"[\n,，;；]+", text)

    seen: set[str] = set()
    result: list[str] = []
    for item in raw_items:
        keyword = item.strip()
        if not keyword:
            continue
        normalized = normalize_text(keyword)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(keyword)
    return result


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"```$", "", text, flags=re.I)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response.")
    snippet = text[start : end + 1]
    return json.loads(snippet)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
