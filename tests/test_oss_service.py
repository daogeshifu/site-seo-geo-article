from pathlib import Path

from app.core.config import Settings
from app.services import oss_service as oss_service_module
from app.services.oss_service import AliyunOSSService


class _RecordingBucket:
    def __init__(self, failures_before_success: int = 0) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0
        self.timeout = None

    def put_object_from_file(self, object_key: str, path: str, headers=None) -> None:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise RuntimeError(f"temporary failure {self.calls}")

    def sign_url(self, method: str, object_key: str, expire_seconds: int) -> str:
        return f"https://signed.example.com/{object_key}?e={expire_seconds}"


class _StubAuth:
    def __init__(self, access_key_id: str, access_key_secret: str) -> None:
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret


class _StubOSS2:
    def __init__(self, bucket: _RecordingBucket) -> None:
        self._bucket = bucket

    Auth = _StubAuth

    def Bucket(self, auth, endpoint: str, bucket_name: str, connect_timeout: int = 0):
        self._bucket.connect_timeout = connect_timeout
        self._bucket.endpoint = endpoint
        self._bucket.bucket_name = bucket_name
        return self._bucket


def test_oss_service_retries_upload_and_applies_timeouts(monkeypatch, tmp_path: Path) -> None:
    local_path = tmp_path / "cover.png"
    local_path.write_bytes(b"fake-image")
    bucket = _RecordingBucket(failures_before_success=2)
    monkeypatch.setattr(oss_service_module, "oss2", _StubOSS2(bucket))
    sleep_calls: list[float] = []
    monkeypatch.setattr(oss_service_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    settings = Settings(
        aliyun_oss_access_key_id="id",
        aliyun_oss_access_key_secret="secret",
        aliyun_oss_endpoint="https://oss-cn-beijing.aliyuncs.com",
        aliyun_oss_bucket="site-seo-geo-article",
        aliyun_oss_connect_timeout=7,
        aliyun_oss_read_timeout=99,
        aliyun_oss_retry_count=3,
        aliyun_oss_retry_delay_seconds=2.5,
    )
    service = AliyunOSSService(settings)

    result = service.upload_file(
        local_path,
        asset_namespace="demo-namespace",
        filename="cover.png",
        mime_type="image/png",
    )

    assert result is not None
    assert result["oss_key"] == "articles/demo-namespace/cover.png"
    assert bucket.calls == 3
    assert bucket.connect_timeout == 7
    assert bucket.timeout == (7, 99)
    assert sleep_calls == [2.5, 2.5]


def test_oss_service_raises_after_last_retry(monkeypatch, tmp_path: Path) -> None:
    local_path = tmp_path / "cover.png"
    local_path.write_bytes(b"fake-image")
    bucket = _RecordingBucket(failures_before_success=5)
    monkeypatch.setattr(oss_service_module, "oss2", _StubOSS2(bucket))
    monkeypatch.setattr(oss_service_module.time, "sleep", lambda seconds: None)

    settings = Settings(
        aliyun_oss_access_key_id="id",
        aliyun_oss_access_key_secret="secret",
        aliyun_oss_endpoint="https://oss-cn-beijing.aliyuncs.com",
        aliyun_oss_bucket="site-seo-geo-article",
        aliyun_oss_retry_count=2,
        aliyun_oss_retry_delay_seconds=0.1,
    )
    service = AliyunOSSService(settings)

    try:
        service.upload_file(
            local_path,
            asset_namespace="demo-namespace",
            filename="cover.png",
            mime_type="image/png",
        )
    except RuntimeError as exc:
        assert "temporary failure 2" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected upload_file to raise after final retry")
