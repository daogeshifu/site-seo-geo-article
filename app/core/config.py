from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8028
    debug: bool = True
    data_dir: Path = Path("data")
    cache_dir: Path = Path("data/cache")
    tasks_dir: Path = Path("data/tasks")
    image_dir: Path = Path("data/images")
    max_workers: int = 2
    llm_mock_mode: bool = True
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    openai_request_timeout: int = 90
    azure_image_api_url: str = ""
    azure_image_api_key: str = ""
    azure_image_endpoint: str = ""
    azure_image_deployment: str = "gpt-image-1.5"
    azure_image_api_version: str = "2025-04-01-preview"
    azure_image_size: str = "1536x1024"
    azure_image_quality: str = "medium"
    azure_image_output_format: str = "png"
    default_content_image_count: int = 3
    normal_access_key: str = ""
    vip_access_key: str = ""
    token_signing_secret: str = ""
    token_ttl_seconds: int = 86400

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("APP_DATA_DIR", "data"))
        normal_access_key = os.getenv("NORMAL_ACCESS_KEY", "").strip()
        vip_access_key = os.getenv("VIP_ACCESS_KEY", "").strip()
        token_signing_secret = os.getenv("TOKEN_SIGNING_SECRET", "").strip() or "||".join(
            item for item in [vip_access_key, normal_access_key, "site-seo-geo-article"] if item
        )
        return cls(
            host=os.getenv("FLASK_HOST", "0.0.0.0"),
            port=int(os.getenv("FLASK_PORT", "8028")),
            debug=os.getenv("FLASK_DEBUG", "true").lower() == "true",
            data_dir=data_dir,
            cache_dir=data_dir / "cache",
            tasks_dir=data_dir / "tasks",
            image_dir=data_dir / "images",
            max_workers=int(os.getenv("MAX_WORKERS", "2")),
            llm_mock_mode=os.getenv("LLM_MOCK_MODE", "true").lower() == "true",
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            openai_request_timeout=int(os.getenv("OPENAI_REQUEST_TIMEOUT", "90")),
            azure_image_api_url=os.getenv("AZURE_IMAGE_API_URL", "").strip(),
            azure_image_api_key=os.getenv("AZURE_IMAGE_API_KEY", "").strip(),
            azure_image_endpoint=os.getenv("AZURE_IMAGE_ENDPOINT", "").strip().rstrip("/"),
            azure_image_deployment=os.getenv("AZURE_IMAGE_DEPLOYMENT", "gpt-image-1.5").strip(),
            azure_image_api_version=os.getenv("AZURE_IMAGE_API_VERSION", "2025-04-01-preview").strip(),
            azure_image_size=os.getenv("AZURE_IMAGE_SIZE", "1536x1024").strip(),
            azure_image_quality=os.getenv("AZURE_IMAGE_QUALITY", "medium").strip(),
            azure_image_output_format=os.getenv("AZURE_IMAGE_OUTPUT_FORMAT", "png").strip(),
            default_content_image_count=max(
                0,
                min(3, int(os.getenv("DEFAULT_CONTENT_IMAGE_COUNT", "3"))),
            ),
            normal_access_key=normal_access_key,
            vip_access_key=vip_access_key,
            token_signing_secret=token_signing_secret,
            token_ttl_seconds=max(60, int(os.getenv("TOKEN_TTL_SECONDS", "86400"))),
        )
