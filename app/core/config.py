from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(slots=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8028
    debug: bool = True
    data_dir: Path = Path("data")
    cache_dir: Path = Path("data/cache")
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
    aliyun_oss_access_key_id: str = ""
    aliyun_oss_access_key_secret: str = ""
    aliyun_oss_endpoint: str = ""
    aliyun_oss_bucket: str = ""
    aliyun_oss_public_base_url: str = ""
    aliyun_oss_prefix: str = "articles"
    aliyun_oss_url_expire_seconds: int = 86400
    default_content_image_count: int = 3
    normal_access_key: str = ""
    vip_access_key: str = ""
    token_signing_secret: str = ""
    token_ttl_seconds: int = 86400
    mysql_host: str = ""
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_database: str = ""
    mysql_charset: str = "utf8mb4"
    mysql_connect_timeout: int = 10
    mysql_read_timeout: int = 20
    mysql_write_timeout: int = 20
    mysql_retry_count: int = 3
    mysql_retry_delay_seconds: float = 0.6
    mysql_pool_size: int = 8
    mysql_fallback_to_memory: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("APP_DATA_DIR", "data"))
        normal_access_key = os.getenv("NORMAL_ACCESS_KEY", "").strip()
        vip_access_key = os.getenv("VIP_ACCESS_KEY", "").strip()
        mysql_user = os.getenv("MYSQL_USER", "").strip()
        token_signing_secret = os.getenv("TOKEN_SIGNING_SECRET", "").strip() or "||".join(
            item for item in [vip_access_key, normal_access_key, "site-seo-geo-article"] if item
        )
        return cls(
            host=os.getenv("FLASK_HOST", "0.0.0.0"),
            port=int(os.getenv("FLASK_PORT", "8028")),
            debug=os.getenv("FLASK_DEBUG", "true").lower() == "true",
            data_dir=data_dir,
            cache_dir=data_dir / "cache",
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
            aliyun_oss_access_key_id=os.getenv("ALIYUN_OSS_ACCESS_KEY_ID", "").strip(),
            aliyun_oss_access_key_secret=os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "").strip(),
            aliyun_oss_endpoint=os.getenv("ALIYUN_OSS_ENDPOINT", "").strip().rstrip("/"),
            aliyun_oss_bucket=os.getenv("ALIYUN_OSS_BUCKET", "").strip(),
            aliyun_oss_public_base_url=os.getenv("ALIYUN_OSS_PUBLIC_BASE_URL", "").strip().rstrip("/"),
            aliyun_oss_prefix=os.getenv("ALIYUN_OSS_PREFIX", "articles").strip().strip("/") or "articles",
            aliyun_oss_url_expire_seconds=max(60, int(os.getenv("ALIYUN_OSS_URL_EXPIRE_SECONDS", "86400"))),
            default_content_image_count=max(
                0,
                min(3, int(os.getenv("DEFAULT_CONTENT_IMAGE_COUNT", "3"))),
            ),
            normal_access_key=normal_access_key,
            vip_access_key=vip_access_key,
            token_signing_secret=token_signing_secret,
            token_ttl_seconds=max(60, int(os.getenv("TOKEN_TTL_SECONDS", "86400"))),
            mysql_host=os.getenv("MYSQL_HOST", "").strip(),
            mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
            mysql_user=mysql_user,
            mysql_password=os.getenv("MYSQL_PASSWORD", "").strip(),
            mysql_database=os.getenv("MYSQL_DATABASE", "").strip() or mysql_user,
            mysql_charset=os.getenv("MYSQL_CHARSET", "utf8mb4").strip() or "utf8mb4",
            mysql_connect_timeout=max(3, int(os.getenv("MYSQL_CONNECT_TIMEOUT", "10"))),
            mysql_read_timeout=max(3, int(os.getenv("MYSQL_READ_TIMEOUT", "20"))),
            mysql_write_timeout=max(3, int(os.getenv("MYSQL_WRITE_TIMEOUT", "20"))),
            mysql_retry_count=max(1, int(os.getenv("MYSQL_RETRY_COUNT", "3"))),
            mysql_retry_delay_seconds=max(0.1, float(os.getenv("MYSQL_RETRY_DELAY_SECONDS", "0.6"))),
            mysql_pool_size=max(1, int(os.getenv("MYSQL_POOL_SIZE", "8"))),
            mysql_fallback_to_memory=_env_bool("MYSQL_FALLBACK_TO_MEMORY", False),
        )
