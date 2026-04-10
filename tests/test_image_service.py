from pathlib import Path

from app.core.config import Settings
from app.services.image_service import ImageService


class _StubOSSService:
    def __init__(self) -> None:
        self.enabled = True
        self.upload_calls: list[tuple[str, str, str]] = []

    def upload_file(self, local_path: Path, *, asset_namespace: str, filename: str, mime_type: str) -> dict[str, str] | None:
        self.upload_calls.append((str(local_path), asset_namespace, filename))
        return {
            "oss_key": f"articles/{asset_namespace}/{filename}",
            "oss_url": f"https://site-seo-geo-article.oss-cn-beijing.aliyuncs.com/articles/{asset_namespace}/{filename}",
        }

    def get_object_url(self, object_key: str) -> str:
        return f"https://signed.example.com/{object_key}"


def test_image_service_uploads_new_assets_to_oss(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, image_dir=tmp_path / "images")
    oss_service = _StubOSSService()
    image_service = ImageService(settings, oss_service=oss_service)

    article = {
        "title": "Portable Charger Guide",
        "images": [],
        "strategy": {"image_briefs": ["Hero visual"]},
    }
    assets = image_service.ensure_assets(
        asset_namespace="demo-namespace",
        category="seo",
        keyword="portable charger",
        info="Brand: VoltGo",
        article=article,
        include_cover=1,
        content_image_count=0,
    )

    assert len(assets) == 1
    assert assets[0]["oss_key"].startswith("articles/demo-namespace/")
    assert assets[0]["oss_url"].startswith("https://site-seo-geo-article.oss-cn-beijing.aliyuncs.com/")
    assert len(oss_service.upload_calls) == 1


def test_image_service_prefers_oss_url_and_lazy_uploads_existing_file(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, image_dir=tmp_path / "images")
    oss_service = _StubOSSService()
    image_service = ImageService(settings, oss_service=oss_service)

    namespace = "demo-namespace"
    folder = settings.image_dir / namespace
    folder.mkdir(parents=True, exist_ok=True)
    local_file = folder / "01-cover-demo.png"
    local_file.write_bytes(b"fake-image-binary")

    response_assets = image_service.build_response_assets(
        [
            {
                "role": "cover",
                "alt": "cover",
                "filename": "01-cover-demo.png",
                "mime_type": "image/png",
            }
        ],
        asset_namespace=namespace,
        include_cover=1,
        content_image_count=0,
    )

    assert len(response_assets) == 1
    assert response_assets[0]["data_url"] == ""
    assert response_assets[0]["url"].startswith("https://signed.example.com/articles/demo-namespace/")
    assert response_assets[0]["oss_key"].startswith("articles/demo-namespace/")
    assert len(oss_service.upload_calls) == 1
