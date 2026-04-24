from __future__ import annotations

MODE_TYPE_KEYWORD = 1
MODE_TYPE_OUTLINE_ARTICLE = 2
MODE_TYPE_OUTLINE_TASK = 3

ARTICLE_MODE_TYPES = {MODE_TYPE_KEYWORD, MODE_TYPE_OUTLINE_ARTICLE}
ALL_MODE_TYPES = {MODE_TYPE_KEYWORD, MODE_TYPE_OUTLINE_ARTICLE, MODE_TYPE_OUTLINE_TASK}


def normalize_mode_type(mode_type: int | None) -> int:
    try:
        value = int(mode_type or MODE_TYPE_KEYWORD)
    except (TypeError, ValueError):
        return MODE_TYPE_KEYWORD
    return value if value in ALL_MODE_TYPES else MODE_TYPE_KEYWORD
