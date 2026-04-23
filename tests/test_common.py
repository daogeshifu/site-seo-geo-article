from app.utils.common import seo_slugify


def test_seo_slugify_lowercase_hyphenated_and_trimmed() -> None:
    slug = seo_slugify("This Is A Very Long SEO Title About Portable Chargers On Planes And Airport Battery Rules 2026")
    assert slug == slug.lower()
    assert " " not in slug
    assert "_" not in slug
    assert "--" not in slug
    assert len(slug) <= 75


def test_seo_slugify_keeps_short_titles_readable() -> None:
    assert seo_slugify("Portable Charger On Plane") == "portable-charger-on-plane"
