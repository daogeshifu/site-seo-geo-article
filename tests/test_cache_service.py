from pathlib import Path

from app.services.cache_service import CacheService


def test_cache_service_uses_same_key_for_equivalent_spacing(tmp_path: Path) -> None:
    cache = CacheService(tmp_path)
    cache.set("seo", "Portable Charger", "Brand: VoltGo", {"title": "A"})

    hit = cache.get("seo", "  portable   charger ", "Brand:  VoltGo")
    assert hit is not None
    assert hit["article"]["title"] == "A"


def test_cache_service_separates_entries_by_access_tier(tmp_path: Path) -> None:
    cache = CacheService(tmp_path)
    cache.set("seo", "Portable Charger", "Brand: VoltGo", {"title": "standard"}, access_tier="standard")
    cache.set("seo", "Portable Charger", "Brand: VoltGo", {"title": "vip"}, access_tier="vip")

    standard_hit = cache.get("seo", "portable charger", "Brand: VoltGo", access_tier="standard")
    vip_hit = cache.get("seo", "portable charger", "Brand: VoltGo", access_tier="vip")

    assert standard_hit is not None
    assert vip_hit is not None
    assert standard_hit["article"]["title"] == "standard"
    assert vip_hit["article"]["title"] == "vip"


def test_cache_service_separates_entries_by_task_context(tmp_path: Path) -> None:
    cache = CacheService(tmp_path)
    cache.set(
        "seo",
        "Portable Charger",
        "Brand: VoltGo",
        {"title": "de"},
        {"country": "de", "article_type": "policy_incentive"},
    )
    cache.set(
        "seo",
        "Portable Charger",
        "Brand: VoltGo",
        {"title": "au"},
        {"country": "nl", "article_type": "natural_disaster"},
    )

    de_hit = cache.get(
        "seo",
        "portable charger",
        "Brand: VoltGo",
        {"country": "de", "article_type": "policy_incentive"},
    )
    au_hit = cache.get(
        "seo",
        "portable charger",
        "Brand: VoltGo",
        {"country": "nl", "article_type": "natural_disaster"},
    )

    assert de_hit is not None
    assert au_hit is not None
    assert de_hit["article"]["title"] == "de"
    assert au_hit["article"]["title"] == "au"
