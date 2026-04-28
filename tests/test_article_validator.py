from app.services.article_validator import ArticleValidator


def test_geo_validator_normalizes_section_order_and_removes_third_party_voice() -> None:
    validator = ArticleValidator()
    article = {
        "title": "Portable Charger on Plane",
        "meta_title": "Portable Charger on Plane",
        "meta_description": "Demo description",
        "strategy": {
            "answer_first_summary": "Portable chargers usually stay allowed when watt-hour and airline rules are clear."
        },
        "raw_html": """
<h1>Portable Charger on Plane</h1>
<p>According to official docs, battery limits depend on watt-hours and airline policy.</p>
<h2>Update log</h2>
<p>Review this later.</p>
<h2>References and citation plan</h2>
<p>Use manufacturer and airline guidance.</p>
<h2>FAQ</h2>
<p>Remove this section.</p>
<h2>Conclusion</h2>
<p>Through official documentation we can conclude that clarity matters.</p>
""",
    }

    normalized = validator.apply(
        article,
        category="geo",
        keyword="portable charger on plane",
        rule_context={},
    )
    html = normalized["raw_html"]

    assert html.index("<h1>Portable Charger on Plane</h1>") < html.index("<strong>Quick Answer:</strong>")
    assert html.index("<strong>Quick Answer:</strong>") < html.index("<h2>References and Evidence to Verify</h2>")
    assert html.index("<h2>References and Evidence to Verify</h2>") < html.index("<h2>FAQ</h2>")
    assert html.index("<h2>FAQ</h2>") < html.index("<h2>Conclusion</h2>")
    assert "<h2>Update log</h2>" not in html
    assert "According to official docs" not in html
    assert "Through official documentation we can conclude that" not in html
    assert "<h3>What should I check first about portable charger on plane?</h3>" in html
    geo_check = next(item for item in normalized["audit"]["checks"] if item["name"] == "geo_structure")
    assert geo_check["passed"] is True


def test_geo_validator_keeps_disclaimer_inside_conclusion() -> None:
    validator = ArticleValidator()
    article = {
        "title": "Solar Rebate Guide",
        "meta_title": "Solar Rebate Guide",
        "meta_description": "Demo description",
        "strategy": {"answer_first_summary": "Check local eligibility and timing before applying."},
        "raw_html": """
<h1>Solar Rebate Guide</h1>
<h2>Quick Answer</h2>
<p>Check local eligibility and timing before applying.</p>
<h2>Eligibility</h2>
<p>Rules vary by program.</p>
<h2>Conclusion</h2>
<p>Act on verified requirements only.</p>
""",
    }

    normalized = validator.apply(
        article,
        category="geo",
        keyword="solar rebate guide",
        rule_context={"required_disclaimer": "Programs change without notice."},
    )
    html = normalized["raw_html"]

    assert "<h2>Disclaimer</h2>" not in html
    assert "<h2>Conclusion</h2><p><strong>Disclaimer:</strong> Programs change without notice.</p>" in html


def test_seo_validator_collapses_dense_body_headings_for_1200_word_article() -> None:
    validator = ArticleValidator()
    article = {
        "title": "Portable Charger Guide",
        "meta_title": "Portable Charger Guide",
        "meta_description": "Demo description",
        "word_limit": 1200,
        "raw_html": """
<h1>Portable Charger Guide</h1>
<p>Intro paragraph one.</p>
<p>Intro paragraph two.</p>
<h2>First section</h2>
<p>Body one.</p>
<p>Body two.</p>
<h2>Second section</h2>
<p>Body one.</p>
<p>Body two.</p>
<h2>Third section</h2>
<p>Short block.</p>
<h2>Fourth section</h2>
<p>Body one.</p>
<p>Body two.</p>
<h2>Conclusion</h2>
<p>Wrap up.</p>
<h2>FAQ</h2>
<h3>Question?</h3>
<p>Answer.</p>
""",
    }

    normalized = validator.apply(
        article,
        category="seo",
        keyword="portable charger",
        rule_context={},
    )
    html = normalized["raw_html"]

    assert html.count("<h2>") == 5
    assert "<h3>Third section</h3>" in html or "<h3>Fourth section</h3>" in html
