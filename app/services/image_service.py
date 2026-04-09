from __future__ import annotations

import base64
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import requests

from app.core.config import Settings
from app.utils.common import ensure_dir, slugify


class ImageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        ensure_dir(settings.image_dir)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.azure_image_api_key and self._generation_url())

    @property
    def mode(self) -> str:
        return "azure" if self.enabled else "mock"

    def ensure_assets(
        self,
        *,
        asset_namespace: str,
        category: str,
        keyword: str,
        info: str,
        article: dict[str, Any],
        include_cover: int,
        content_image_count: int,
    ) -> list[dict[str, Any]]:
        normalized_assets = [
            self._normalize_asset(asset, asset_namespace)
            for asset in article.get("images") or []
            if asset.get("filename")
        ]
        assets = list(normalized_assets)

        requested_cover = max(0, min(1, int(include_cover)))
        requested_content_count = max(0, min(3, int(content_image_count)))
        prompts = self._build_prompts(
            category=category,
            keyword=keyword,
            info=info,
            article=article,
            include_cover=requested_cover,
            content_image_count=requested_content_count,
        )

        existing_cover = next((item for item in assets if item["role"] == "cover"), None)
        if requested_cover and not existing_cover:
            cover_spec = next((item for item in prompts if item["role"] == "cover"), None)
            if cover_spec:
                assets.append(
                    self._create_asset(
                        asset_namespace=asset_namespace,
                        keyword=keyword,
                        role="cover",
                        prompt=cover_spec["prompt"],
                        alt=cover_spec["alt"],
                        index=len(assets) + 1,
                    )
                )

        existing_content = [item for item in assets if item["role"] == "content"]
        for prompt_spec in [item for item in prompts if item["role"] == "content"][len(existing_content) :]:
            assets.append(
                self._create_asset(
                    asset_namespace=asset_namespace,
                    keyword=keyword,
                    role="content",
                    prompt=prompt_spec["prompt"],
                    alt=prompt_spec["alt"],
                    index=len(assets) + 1,
                )
            )

        return self._sort_assets(assets)

    def build_response_assets(
        self,
        assets: list[dict[str, Any]],
        *,
        asset_namespace: str,
        include_cover: int,
        content_image_count: int,
    ) -> list[dict[str, Any]]:
        selected = self._select_assets(
            assets,
            include_cover=max(0, min(1, int(include_cover))),
            content_image_count=max(0, min(3, int(content_image_count))),
        )
        hydrated: list[dict[str, Any]] = []
        for asset in selected:
            normalized = self._normalize_asset(asset, asset_namespace)
            data_url = self._build_data_url(normalized)
            normalized["data_url"] = data_url
            normalized["url"] = data_url
            hydrated.append(normalized)
        return hydrated

    def inject_images_into_html(self, html: str, assets: list[dict[str, Any]]) -> str:
        if not html.strip():
            return html

        clean_html = self.strip_generated_images(html)
        if not assets:
            return clean_html

        result = clean_html.strip()
        cover = next((item for item in assets if item["role"] == "cover"), None)
        content_images = [item for item in assets if item["role"] == "content"]

        if cover:
            cover_tag = self._build_image_tag(cover, "cover")
            if "</p>" in result:
                result = result.replace("</p>", f'</p>\n{cover_tag}', 1)
            elif "</h1>" in result:
                result = result.replace("</h1>", f"</h1>\n{cover_tag}", 1)
            else:
                result = cover_tag + "\n" + result

        if not content_images:
            return result

        matches = list(re.finditer(r"<h2\b[^>]*>", result, flags=re.IGNORECASE))
        if not matches:
            image_block = "\n".join(self._build_image_tag(item, "content") for item in content_images)
            return result + "\n" + image_block

        insert_points = matches[1:] if len(matches) > 1 else matches
        insertions = list(zip(insert_points, content_images))
        for match, image in reversed(insertions):
            result = result[: match.start()] + self._build_image_tag(image, "content") + "\n" + result[match.start() :]

        if len(content_images) > len(insertions):
            for image in content_images[len(insertions) :]:
                result += "\n" + self._build_image_tag(image, "content")

        return result

    def strip_generated_images(self, html: str) -> str:
        return re.sub(r'<img class="article-generated-image[^"]*"[^>]*>\s*', "", html or "", flags=re.IGNORECASE)

    def _build_prompts(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        article: dict[str, Any],
        include_cover: int,
        content_image_count: int,
    ) -> list[dict[str, str]]:
        title = article.get("title") or keyword
        strategy = article.get("strategy") or {}
        image_briefs = strategy.get("image_briefs") if isinstance(strategy.get("image_briefs"), list) else []
        outline = strategy.get("outline") if isinstance(strategy.get("outline"), list) else []
        usable_outline_titles = [
            item.get("title", "")
            for item in outline
            if str(item.get("level", "")).upper() == "H2"
            and item.get("title")
            and item.get("title", "").lower() not in {"conclusion", "faq"}
        ]

        brand_context = info.strip() or "Keep the image brand-neutral, editorial, and clean."
        prompts: list[dict[str, str]] = []
        if include_cover:
            prompts.append(
                {
                    "role": "cover",
                    "alt": f"{keyword} cover illustration",
                    "prompt": (
                        f"Create a polished editorial cover image for an article about '{title}'. "
                        f"Topic keyword: '{keyword}'. Context: {brand_context}. "
                        "Style: premium website hero image, modern, realistic, professional, no text, no watermark, no logo overlay."
                    ),
                }
            )

        content_briefs = [brief for brief in image_briefs if isinstance(brief, str) and brief.strip()][:content_image_count]
        if len(content_briefs) < content_image_count:
            for title_item in usable_outline_titles:
                if len(content_briefs) >= content_image_count:
                    break
                content_briefs.append(title_item)

        while len(content_briefs) < content_image_count:
            content_briefs.append(f"Editorial supporting visual for {keyword}")

        for idx, brief in enumerate(content_briefs, start=1):
            if category == "geo":
                prompt = (
                    f"Create a clean supporting image for a GEO article about '{keyword}'. "
                    f"Focus on this section: {brief}. Context: {brand_context}. "
                    "Style: realistic editorial illustration, clear subject, trustworthy, no text, no watermark."
                )
            else:
                prompt = (
                    f"Create a clean supporting image for an SEO article about '{keyword}'. "
                    f"Focus on this section: {brief}. Context: {brand_context}. "
                    "Style: modern editorial website image, realistic, professional, no text, no watermark."
                )
            prompts.append(
                {
                    "role": "content",
                    "alt": f"{keyword} supporting image {idx}",
                    "prompt": prompt,
                }
            )
        return prompts

    def _create_asset(
        self,
        *,
        asset_namespace: str,
        keyword: str,
        role: str,
        prompt: str,
        alt: str,
        index: int,
    ) -> dict[str, Any]:
        binary, mime_type, extension, source = self._generate_binary(prompt, role, keyword, index)
        filename = f"{index:02d}-{role}-{slugify(keyword)[:48]}.{extension}"
        folder = self.settings.image_dir / asset_namespace
        ensure_dir(folder)
        path = folder / filename
        path.write_bytes(binary)
        return {
            "role": role,
            "alt": alt,
            "prompt": prompt,
            "filename": filename,
            "mime_type": mime_type,
            "source": source,
            "asset_namespace": asset_namespace,
            "asset_uri": f"asset://{asset_namespace}/{filename}",
        }

    def _select_assets(
        self,
        assets: list[dict[str, Any]],
        *,
        include_cover: int,
        content_image_count: int,
    ) -> list[dict[str, Any]]:
        ordered = self._sort_assets(
            [asset for asset in assets if asset.get("filename")]
        )
        selected: list[dict[str, Any]] = []
        if include_cover:
            cover = next((item for item in ordered if item.get("role") == "cover"), None)
            if cover:
                selected.append(cover)

        content_assets = [item for item in ordered if item.get("role") == "content"][:content_image_count]
        selected.extend(content_assets)
        return selected

    def _sort_assets(self, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def sort_key(item: dict[str, Any]) -> tuple[int, str]:
            role_weight = 0 if item.get("role") == "cover" else 1
            return (role_weight, item.get("filename", ""))

        return sorted(assets, key=sort_key)

    def _normalize_asset(self, asset: dict[str, Any], asset_namespace: str) -> dict[str, Any]:
        normalized = deepcopy(asset)
        namespace = normalized.get("asset_namespace") or asset_namespace
        filename = normalized.get("filename", "")
        normalized["asset_namespace"] = namespace
        normalized["asset_uri"] = normalized.get("asset_uri") or f"asset://{namespace}/{filename}"
        return normalized

    def _build_data_url(self, asset: dict[str, Any]) -> str:
        namespace = asset.get("asset_namespace")
        filename = asset.get("filename")
        if not namespace or not filename:
            return ""
        path = self.settings.image_dir / namespace / filename
        if not path.exists():
            return ""
        mime_type = asset.get("mime_type") or self._guess_mime_type(path)
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _build_image_tag(self, asset: dict[str, Any], variant: str) -> str:
        src = asset.get("data_url") or asset.get("url") or asset.get("asset_uri") or ""
        return (
            f'<img class="article-generated-image article-generated-image--{variant}" '
            f'src="{src}" alt="{self._escape_attr(asset["alt"])}" />'
        )

    def _generate_binary(self, prompt: str, role: str, keyword: str, index: int) -> tuple[bytes, str, str, str]:
        if self.enabled:
            return self._generate_live_image(prompt)
        return self._generate_mock_image(prompt, role, keyword, index)

    def _generate_live_image(self, prompt: str) -> tuple[bytes, str, str, str]:
        response = requests.post(
            self._generation_url(),
            headers={
                "Api-Key": self.settings.azure_image_api_key,
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "n": 1,
                "size": self.settings.azure_image_size,
                "quality": self.settings.azure_image_quality,
                "output_format": self.settings.azure_image_output_format,
            },
            timeout=self.settings.openai_request_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            error = payload["error"]
            raise RuntimeError(error.get("message") or error.get("code") or "Azure image generation failed.")
        data = payload.get("data") or []
        if not data or not data[0].get("b64_json"):
            raise RuntimeError("Azure image response did not include b64_json.")
        binary = base64.b64decode(data[0]["b64_json"])
        extension = self.settings.azure_image_output_format.lower()
        mime_type = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "webp": "image/webp",
        }.get(extension, "image/png")
        return binary, mime_type, extension, "azure"

    def _generate_mock_image(
        self,
        prompt: str,
        role: str,
        keyword: str,
        index: int,
    ) -> tuple[bytes, str, str, str]:
        lines = [
            "SEO / GEO Image",
            role.upper(),
            keyword[:48],
            prompt[:100],
        ]
        safe_lines = [self._escape_attr(item) for item in lines]
        svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024" viewBox="0 0 1536 1024">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a" />
      <stop offset="100%" stop-color="#0ea5e9" />
    </linearGradient>
  </defs>
  <rect width="1536" height="1024" fill="url(#bg)" rx="28" />
  <circle cx="{220 + index * 48}" cy="180" r="120" fill="rgba(255,255,255,0.10)" />
  <circle cx="1290" cy="820" r="160" fill="rgba(255,255,255,0.08)" />
  <rect x="96" y="96" width="1344" height="832" rx="40" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.16)" />
  <text x="136" y="210" fill="#ffffff" font-size="62" font-family="Arial, sans-serif" font-weight="700">{safe_lines[0]}</text>
  <text x="136" y="300" fill="#bfdbfe" font-size="44" font-family="Arial, sans-serif" font-weight="700">{safe_lines[1]}</text>
  <text x="136" y="390" fill="#e2e8f0" font-size="36" font-family="Arial, sans-serif">{safe_lines[2]}</text>
  <foreignObject x="136" y="460" width="1160" height="320">
    <div xmlns="http://www.w3.org/1999/xhtml" style="color:#dbeafe;font:28px Arial,sans-serif;line-height:1.45;">
      {safe_lines[3]}
    </div>
  </foreignObject>
</svg>
""".strip()
        return svg.encode("utf-8"), "image/svg+xml", "svg", "mock"

    def _generation_url(self) -> str:
        if self.settings.azure_image_api_url:
            return self.settings.azure_image_api_url
        if self.settings.azure_image_endpoint and self.settings.azure_image_deployment:
            return (
                f"{self.settings.azure_image_endpoint}/openai/deployments/"
                f"{self.settings.azure_image_deployment}/images/generations"
                f"?api-version={self.settings.azure_image_api_version}"
            )
        return ""

    def _guess_mime_type(self, path: Path) -> str:
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "application/octet-stream")

    def _escape_attr(self, value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
