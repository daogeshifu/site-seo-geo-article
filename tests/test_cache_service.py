from pathlib import Path

from seo_geo_writer.cache_service import CacheService


def test_cache_service_uses_same_key_for_equivalent_spacing(tmp_path: Path) -> None:
    cache = CacheService(tmp_path)
    cache.set("seo", "Portable Charger", "Brand: VoltGo", {"title": "A"})

    hit = cache.get("seo", "  portable   charger ", "Brand:  VoltGo")
    assert hit is not None
    assert hit["article"]["title"] == "A"

