from __future__ import annotations

import base64
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import requests

from app.core.config import Settings
from app.services.oss_service import AliyunOSSService
from app.utils.common import ensure_dir, slugify


class ImageService:
    """负责文章图片的生成、存储与注入。

    支持两种模式：
    - azure: 通过 Azure OpenAI DALL-E 接口生成真实图片
    - mock:  在 API 凭据缺失时生成占位 SVG，供本地开发使用
    """

    def __init__(self, settings: Settings, oss_service: AliyunOSSService | None = None) -> None:
        self.settings = settings
        self.oss_service = oss_service
        ensure_dir(settings.image_dir)

    @property
    def enabled(self) -> bool:
        """是否已配置 Azure 图片生成凭据。"""
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
        """确保文章所需的图片资产均已生成并落盘。

        幂等性：已存在的图片（article["images"] 中有 filename 的条目）会直接复用，
        只对缺少的部分调用生成接口，避免重复计费。
        """
        # 从文章元数据中还原已有资产，补全 namespace / uri 字段
        assets = [
            self._normalize_asset(asset, asset_namespace)
            for asset in article.get("images") or []
            if asset.get("filename")
        ]

        # 将入参限制在合法范围内再使用
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

        # 封面：不存在时才生成，避免重复
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

        # 内容图：跳过已有的，只补充差额部分
        existing_content_count = sum(1 for item in assets if item["role"] == "content")
        pending_content_prompts = [
            item for item in prompts if item["role"] == "content"
        ][existing_content_count:]

        for prompt_spec in pending_content_prompts:
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
        """从已有资产列表中按需筛选，并优先返回 OSS 地址，未配置 OSS 时退回 data URL。"""
        selected = self._select_assets(
            assets,
            include_cover=max(0, min(1, int(include_cover))),
            content_image_count=max(0, min(3, int(content_image_count))),
        )
        hydrated: list[dict[str, Any]] = []
        for asset in selected:
            normalized = self._normalize_asset(asset, asset_namespace)
            file_path = self._asset_path(normalized)
            remote_url = self._ensure_remote_url(normalized, file_path=file_path)
            data_url = "" if remote_url else self._build_data_url(normalized, file_path=file_path)
            normalized["data_url"] = data_url
            normalized["url"] = remote_url or data_url or normalized.get("asset_uri", "")
            hydrated.append(normalized)
        return hydrated

    def inject_images_into_html(self, html: str, assets: list[dict[str, Any]]) -> str:
        """将封面图和内容图插入 HTML 字符串的合适位置。

        插入策略：
        - 封面图：插在第一个 </p> 或 </h1> 之后；若均不存在则置于文章开头。
        - 内容图：插在第 2 个及之后的 <h2> 标签之前（跳过第一个 H2，避免与封面图紧挨）；
          若 <h2> 数量不足，多余的内容图追加到文章末尾。
        - 先调用 strip_generated_images 清除旧图，保持幂等。
        """
        if not html.strip():
            return html

        result = self.strip_generated_images(html).strip()
        if not assets:
            return result

        cover = next((item for item in assets if item["role"] == "cover"), None)
        content_images = [item for item in assets if item["role"] == "content"]

        if cover:
            cover_tag = self._build_image_tag(cover, "cover")
            if "</p>" in result:
                result = result.replace("</p>", f"</p>\n{cover_tag}", 1)
            elif "</h1>" in result:
                result = result.replace("</h1>", f"</h1>\n{cover_tag}", 1)
            else:
                result = cover_tag + "\n" + result

        if not content_images:
            return result

        matches = list(re.finditer(r"<h2\b[^>]*>", result, flags=re.IGNORECASE))
        if not matches:
            # 文章没有 H2 结构，直接追加到末尾
            image_block = "\n".join(self._build_image_tag(item, "content") for item in content_images)
            return result + "\n" + image_block

        # 跳过第一个 H2（通常紧随封面或引言），从第二个 H2 开始插入
        insert_points = matches[1:] if len(matches) > 1 else matches
        insertions = list(zip(insert_points, content_images))

        # 逆序插入，防止字符串偏移量失效
        for match, image in reversed(insertions):
            result = result[: match.start()] + self._build_image_tag(image, "content") + "\n" + result[match.start():]

        # H2 锚点不足时，将剩余图片追加到文章末尾
        for image in content_images[len(insertions):]:
            result += "\n" + self._build_image_tag(image, "content")

        return result

    def strip_generated_images(self, html: str) -> str:
        """移除 HTML 中所有由本服务生成的 <img> 标签（class 以 article-generated-image 开头）。"""
        return re.sub(r'<img class="article-generated-image[^"]*"[^>]*>\s*', "", html or "", flags=re.IGNORECASE)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

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
        """根据文章策略数据构造图片生成提示词列表。

        内容图 brief 的填充优先级：
        1. strategy.image_briefs（AI 预先规划的图片描述）
        2. strategy.outline 中的 H2 标题（排除 Conclusion / FAQ）
        3. 通用兜底文案
        """
        title = article.get("title") or keyword
        strategy = article.get("strategy") or {}

        image_briefs = strategy.get("image_briefs") if isinstance(strategy.get("image_briefs"), list) else []
        outline = strategy.get("outline") if isinstance(strategy.get("outline"), list) else []

        # 从大纲中提取可用的 H2 标题作为备用 brief 来源
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

        # 按优先级填充内容图 brief，直到满足数量要求
        content_briefs = [brief for brief in image_briefs if isinstance(brief, str) and brief.strip()][:content_image_count]

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
        """生成单张图片并写入磁盘，返回资产描述字典。"""
        binary, mime_type, extension, source = self._generate_binary(prompt, role, keyword, index)
        filename = f"{index:02d}-{role}-{slugify(keyword)[:48]}.{extension}"
        folder = self.settings.image_dir / asset_namespace
        ensure_dir(folder)
        local_path = folder / filename
        local_path.write_bytes(binary)
        asset = {
            "role": role,
            "alt": alt,
            "prompt": prompt,
            "filename": filename,
            "mime_type": mime_type,
            "source": source,
            "asset_namespace": asset_namespace,
            "asset_uri": f"asset://{asset_namespace}/{filename}",
        }
        remote = self._upload_to_oss(asset, local_path=local_path)
        if remote:
            asset.update(remote)
        return asset

    def _select_assets(
        self,
        assets: list[dict[str, Any]],
        *,
        include_cover: int,
        content_image_count: int,
    ) -> list[dict[str, Any]]:
        """从资产列表中按角色和数量筛选，过滤掉没有落盘文件的条目。"""
        ordered = self._sort_assets([asset for asset in assets if asset.get("filename")])
        selected: list[dict[str, Any]] = []

        if include_cover:
            cover = next((item for item in ordered if item.get("role") == "cover"), None)
            if cover:
                selected.append(cover)

        content_assets = [item for item in ordered if item.get("role") == "content"][:content_image_count]
        selected.extend(content_assets)
        return selected

    def _sort_assets(self, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """封面图排在内容图之前，同角色按文件名字典序排列。"""
        def sort_key(item: dict[str, Any]) -> tuple[int, str]:
            role_weight = 0 if item.get("role") == "cover" else 1
            return (role_weight, item.get("filename", ""))

        return sorted(assets, key=sort_key)

    def _normalize_asset(self, asset: dict[str, Any], asset_namespace: str) -> dict[str, Any]:
        """补全资产的 asset_namespace 和 asset_uri 字段（深拷贝，不修改原对象）。"""
        normalized = deepcopy(asset)
        namespace = normalized.get("asset_namespace") or asset_namespace
        filename = normalized.get("filename", "")
        normalized["asset_namespace"] = namespace
        normalized["asset_uri"] = normalized.get("asset_uri") or f"asset://{namespace}/{filename}"
        return normalized

    def _build_data_url(self, asset: dict[str, Any], *, file_path: Path | None = None) -> str:
        """将磁盘上的图片文件读取并编码为 data URL；文件不存在时返回空字符串。"""
        path = file_path or self._asset_path(asset)
        if not path.exists():
            return ""
        mime_type = asset.get("mime_type") or self._guess_mime_type(path)
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _build_image_tag(self, asset: dict[str, Any], variant: str) -> str:
        """生成带 CSS 类名的 <img> 标签，src 优先使用 data URL，降级到 asset URI。"""
        src = asset.get("data_url") or asset.get("url") or asset.get("asset_uri") or ""
        return (
            f'<img class="article-generated-image article-generated-image--{variant}" '
            f'src="{src}" alt="{self._escape_attr(asset["alt"])}" />'
        )

    def _asset_path(self, asset: dict[str, Any]) -> Path:
        namespace = asset.get("asset_namespace")
        filename = asset.get("filename")
        if not namespace or not filename:
            return self.settings.image_dir / "__missing__"
        return self.settings.image_dir / namespace / filename

    def _upload_to_oss(self, asset: dict[str, Any], *, local_path: Path) -> dict[str, str] | None:
        if not self.oss_service or not self.oss_service.enabled:
            return None
        if asset.get("oss_key") and asset.get("oss_url"):
            return {"oss_key": asset["oss_key"], "oss_url": asset["oss_url"]}
        return self.oss_service.upload_file(
            local_path,
            asset_namespace=asset["asset_namespace"],
            filename=asset["filename"],
            mime_type=asset.get("mime_type") or self._guess_mime_type(local_path),
        )

    def _ensure_remote_url(self, asset: dict[str, Any], *, file_path: Path) -> str:
        if not self.oss_service or not self.oss_service.enabled:
            return asset.get("oss_url", "")
        oss_key = asset.get("oss_key")
        if not oss_key and file_path.exists():
            uploaded = self._upload_to_oss(asset, local_path=file_path)
            if uploaded:
                asset.update(uploaded)
                oss_key = uploaded.get("oss_key")
        if asset.get("oss_url") and self.settings.aliyun_oss_public_base_url:
            return asset["oss_url"]
        if oss_key:
            fresh_url = self.oss_service.get_object_url(oss_key)
            asset["oss_url"] = fresh_url
            return fresh_url
        return ""

    def _generate_binary(self, prompt: str, role: str, keyword: str, index: int) -> tuple[bytes, str, str, str]:
        """根据当前模式分发到真实生成或 mock 生成。"""
        if self.enabled:
            return self._generate_live_image(prompt)
        return self._generate_mock_image(prompt, role, keyword, index)

    def _generate_live_image(self, prompt: str) -> tuple[bytes, str, str, str]:
        """调用 Azure DALL-E 接口生成图片，返回 (二进制, mime_type, 扩展名, 来源标记)。

        双重错误检查：
        1. HTTP 层：response.raise_for_status() 捕获 4xx/5xx
        2. 业务层：payload["error"] 捕获接口返回的逻辑错误（HTTP 200 但内容报错）
        """
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
        """在无 API 凭据时生成带调试信息的 SVG 占位图。

        圆形装饰元素的 cx 随 index 偏移，方便在页面上区分不同图片。
        """
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
        """优先使用完整的 api_url；若未配置则从 endpoint + deployment 拼接标准路径。"""
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
        """对 HTML 属性值中的特殊字符进行转义，防止 XSS。"""
        return (
            str(value)
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
