from __future__ import annotations

import logging
import time
from pathlib import Path

from app.core.config import Settings

try:
    import oss2
except ImportError:  # pragma: no cover - optional runtime dependency
    oss2 = None

logger = logging.getLogger(__name__)


class AliyunOSSService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._bucket = None

    @property
    def enabled(self) -> bool:
        return bool(
            oss2 is not None
            and self.settings.aliyun_oss_access_key_id
            and self.settings.aliyun_oss_access_key_secret
            and self.settings.aliyun_oss_endpoint
            and self.settings.aliyun_oss_bucket
        )

    def upload_file(self, local_path: Path, *, asset_namespace: str, filename: str, mime_type: str) -> dict[str, str] | None:
        if not self.enabled or not local_path.exists():
            return None
        object_key = self._build_object_key(asset_namespace=asset_namespace, filename=filename)
        headers = {"Content-Type": mime_type} if mime_type else None
        bucket = self._get_bucket()
        bucket.timeout = (
            self.settings.aliyun_oss_connect_timeout,
            self.settings.aliyun_oss_read_timeout,
        )
        last_error: Exception | None = None
        for attempt in range(1, self.settings.aliyun_oss_retry_count + 1):
            try:
                bucket.put_object_from_file(object_key, str(local_path), headers=headers)
                break
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.aliyun_oss_retry_count:
                    raise
                logger.warning(
                    "OSS upload attempt %s/%s failed for %s; retrying in %.1fs",
                    attempt,
                    self.settings.aliyun_oss_retry_count,
                    object_key,
                    self.settings.aliyun_oss_retry_delay_seconds,
                    exc_info=True,
                )
                time.sleep(self.settings.aliyun_oss_retry_delay_seconds)
        if last_error and self.settings.aliyun_oss_retry_count < 1:
            raise last_error
        return {
            "oss_key": object_key,
            "oss_url": self.get_object_url(object_key),
        }

    def get_object_url(self, object_key: str) -> str:
        if not object_key:
            return ""
        if self.settings.aliyun_oss_public_base_url:
            return f"{self.settings.aliyun_oss_public_base_url.rstrip('/')}/{object_key}"
        if not self.enabled:
            return ""
        return self._get_bucket().sign_url("GET", object_key, self.settings.aliyun_oss_url_expire_seconds)

    def _build_object_key(self, *, asset_namespace: str, filename: str) -> str:
        prefix = self.settings.aliyun_oss_prefix.strip("/")
        if prefix:
            return f"{prefix}/{asset_namespace}/{filename}"
        return f"{asset_namespace}/{filename}"

    def _get_bucket(self):
        if self._bucket is None:
            auth = oss2.Auth(
                self.settings.aliyun_oss_access_key_id,
                self.settings.aliyun_oss_access_key_secret,
            )
            self._bucket = oss2.Bucket(
                auth,
                self.settings.aliyun_oss_endpoint,
                self.settings.aliyun_oss_bucket,
                connect_timeout=self.settings.aliyun_oss_connect_timeout,
            )
        return self._bucket
