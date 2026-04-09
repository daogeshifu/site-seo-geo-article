from __future__ import annotations

from typing import Any


def build_demo_page_context(
    *, llm_enabled: bool, image_enabled: bool, image_mode: str
) -> dict[str, Any]:
    llm_label = "Live LLM" if llm_enabled else "Mock Mode"
    llm_badge_class = "badge-live" if llm_enabled else "badge-mock"
    llm_tip = (
        "Real model calls are enabled. The generated output comes from your configured OpenAI-compatible endpoint."
        if llm_enabled
        else "No API key is configured, so the demo is currently using mock article output for safe local testing."
    )
    image_label = "Azure Images" if image_enabled else "Mock Images"
    image_badge_class = "badge-live" if image_enabled else "badge-mock"
    image_tip = (
        "Azure OpenAI image generation is active. Each task can request an optional cover plus 0-3 supporting images."
        if image_enabled
        else "Azure image credentials are not configured, so the app will generate local SVG mock images for demo use."
    )

    return {
        "page_title": "SEO / GEO Article Writer Console",
        "llm_label": llm_label,
        "llm_badge_class": llm_badge_class,
        "llm_tip": llm_tip,
        "image_label": image_label,
        "image_badge_class": image_badge_class,
        "image_tip": image_tip,
        "image_mode": image_mode,
    }
