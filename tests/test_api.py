import time
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.factory import create_app


def issue_token(client: TestClient) -> dict:
    response = client.post("/api/token", json={"access_key": "test-vip-key"})
    assert response.status_code == 200
    return response.json()["data"]


def issue_standard_token(client: TestClient) -> dict:
    response = client.post("/api/token", json={"access_key": "test-standard-key"})
    assert response.status_code == 200
    return response.json()["data"]


def wait_for_task_completion(client: TestClient, bearer: dict[str, str], task_id: int, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task_response = client.get(f"/api/tasks/{task_id}", headers=bearer)
        assert task_response.status_code == 200
        body = task_response.json()
        if body.get("success") is False and body.get("status") in {"queued", "running"}:
            time.sleep(0.1)
            continue
        return body["data"]
    raise AssertionError("task did not finish within timeout")


def wait_for_outline_completion(
    client: TestClient,
    bearer: dict[str, str],
    outline_id: int,
    timeout: float = 5.0,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        outline_response = client.get(f"/api/outline/{outline_id}", headers=bearer)
        assert outline_response.status_code == 200
        body = outline_response.json()
        if body.get("success") is False and body.get("status") in {"queued", "running"}:
            time.sleep(0.1)
            continue
        return body["data"]
    raise AssertionError("outline did not finish within timeout")


def test_create_task_and_fetch_result(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)

    unauthorized_response = client.post(
        "/api/tasks",
        json={
            "category": "geo",
            "keyword": "portable charger on plane",
            "info": "Brand: VoltGo",
        },
    )
    assert unauthorized_response.status_code == 401

    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    create_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "geo",
            "keyword": "portable charger on plane",
            "info": "Brand: VoltGo",
            "include_cover": 1,
            "content_image_count": 2,
            "task_context": {
                "country": "de",
                "requires_shopify_link": True,
                "shopify_url": "https://de.ecoflow.com/products/stream-microinverter",
                "ai_qa_content": "AI answer: airline portable chargers are mostly limited by watt-hours.",
                "ai_qa_source": "https://www.faa.gov/hazmat/packsafe/lithium-batteries",
            },
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["task_id"]
    assert create_response.json()["data"]["access_tier"] == "vip"
    assert create_response.json()["data"]["mode_type"] == 1

    task_payload = wait_for_task_completion(client, bearer, task_id)
    status = task_payload["status"]
    assert status == "completed"
    assert task_payload is not None
    assert task_payload["access_tier"] == "vip"
    assert task_payload["keyword"] == "portable charger on plane"
    assert task_payload["mode_type"] == 1
    assert task_payload["provider"] == "openai:gpt-4.1-mini"
    assert task_payload["word_limit"] == 1200
    assert task_payload["task_context"]["country"] == "de"
    assert "watt-hours" in task_payload["task_context"]["ai_qa_content"]
    assert task_payload["task_context"]["ai_qa_source"].startswith("https://www.faa.gov")
    assert task_payload["article"]["generation_mode"] == "mock"
    assert task_payload["article"]["slug"] == task_payload["article"]["slug"].lower()
    assert " " not in task_payload["article"]["slug"]
    assert len(task_payload["article"]["slug"]) <= 75
    assert task_payload["article"]["audit"]["score"] > 0
    assert "https://de.ecoflow.com/products/stream-microinverter" in task_payload["article"]["raw_html"]
    raw_html = task_payload["article"]["raw_html"]
    assert raw_html.index("<h1>") < raw_html.index("<strong>Quick Answer:</strong>")
    assert raw_html.index("<strong>Quick Answer:</strong>") < raw_html.index("<h2>References and Evidence to Verify</h2>")
    assert raw_html.index("<h2>References and Evidence to Verify</h2>") < raw_html.index("<h2>FAQ</h2>")
    assert raw_html.index("<h2>FAQ</h2>") < raw_html.index("<h2>Conclusion</h2>")
    assert "<h3>What should I check first about portable charger on plane?</h3>" in raw_html
    assert "<h2>Update log</h2>" not in raw_html
    assert len(task_payload["article"]["images"]) == 3
    assert task_payload["article"]["cover_image"] is not None
    assert len(task_payload["article"]["content_images"]) == 2
    assert task_payload["article"]["images"][0]["data_url"].startswith("data:image/")


def test_task_can_disable_cover_and_content_images(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    create_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "best usb c charger",
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["task_id"]

    task_payload = wait_for_task_completion(client, bearer, task_id)

    article = task_payload["article"]
    assert article["images"] == []
    assert article["cover_image"] is None
    assert article["content_images"] == []
    assert article["image_generation_mode"] == "disabled"


def test_create_task_requires_keyword_field(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    create_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keywords": ["best usb c charger"],
            "info": "Brand: VoltGo",
        },
    )
    assert create_response.status_code == 422


def test_get_task_returns_false_while_running(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    original_generate = app.state.services.writer_service.generate

    def delayed_generate(*args, **kwargs):
        time.sleep(0.25)
        return original_generate(*args, **kwargs)

    app.state.services.writer_service.generate = delayed_generate
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    create_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "best usb c charger",
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["task_id"]

    task_response = client.get(f"/api/tasks/{task_id}", headers=bearer)
    assert task_response.status_code == 200
    payload = task_response.json()
    assert payload["success"] is False
    assert payload["message"] == "task not completed"
    assert payload["status"] in {"queued", "running"}


def test_reuse_existing_task_when_force_refresh_is_false(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    first_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "best usb c charger",
            "info": "Brand: VoltGo",
            "language": "English",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert first_response.status_code == 200
    first_task_id = first_response.json()["data"]["task_id"]
    first_task = wait_for_task_completion(client, bearer, first_task_id)
    assert first_task["status"] == "completed"

    second_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "best usb c charger",
            "info": "Brand: VoltGo",
            "language": "English",
            "include_cover": 1,
            "content_image_count": 3,
            "force_refresh": False,
        },
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()["data"]
    assert second_payload["task_id"] == first_task_id
    assert second_payload["status"] == "completed"

    third_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "best usb c charger",
            "info": "Brand: VoltGo",
            "language": "English",
            "force_refresh": True,
        },
    )
    assert third_response.status_code == 200
    third_task_id = third_response.json()["data"]["task_id"]
    assert third_task_id != first_task_id


def test_word_limit_creates_distinct_task_when_changed(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    first_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "word limit test keyword",
            "info": "Brand: VoltGo",
            "language": "English",
            "word_limit": 1200,
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert first_response.status_code == 200
    first_task_id = first_response.json()["data"]["task_id"]
    first_task = wait_for_task_completion(client, bearer, first_task_id)
    assert first_task["status"] == "completed"
    assert first_task["word_limit"] == 1200

    second_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "word limit test keyword",
            "info": "Brand: VoltGo",
            "language": "English",
            "word_limit": 1800,
            "force_refresh": False,
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert second_response.status_code == 200
    second_task_id = second_response.json()["data"]["task_id"]
    assert second_task_id != first_task_id
    second_task = wait_for_task_completion(client, bearer, second_task_id)
    assert second_task["word_limit"] == 1800


def test_mode_type_changes_cache_scope_and_outline_mode_preserves_headings(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    first_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "portable charger on plane",
            "mode_type": 1,
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert first_response.status_code == 200
    first_task_id = first_response.json()["data"]["task_id"]
    wait_for_task_completion(client, bearer, first_task_id)

    second_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "# Portable Charger on Plane\n## Airline rules\n## Battery limits\n### Domestic flights",
            "mode_type": 2,
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert second_response.status_code == 200
    second_task_id = second_response.json()["data"]["task_id"]
    assert second_task_id != first_task_id

    second_task = wait_for_task_completion(client, bearer, second_task_id)
    assert second_task["mode_type"] == 2
    assert second_task["article"]["mode_type"] == 2
    html = second_task["article"]["raw_html"]
    assert "<h1>Portable Charger on Plane</h1>" in html
    assert "<h2>Airline rules</h2>" in html
    assert "<h2>Battery limits</h2>" in html
    assert "<h3>Domestic flights</h3>" in html
    assert html.index("<h2>Airline rules</h2>") < html.index("<h2>Battery limits</h2>")


def test_create_task_accepts_outline_in_keyword_field_for_outline_mode(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "## Airline rules\n## Battery limits",
            "mode_type": 2,
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert response.status_code == 200
    task_id = response.json()["data"]["task_id"]
    assert response.json()["data"]["mode_type"] == 2
    task_payload = wait_for_task_completion(client, bearer, task_id)
    assert task_payload["mode_type"] == 2
    assert "<h2>Airline rules</h2>" in task_payload["article"]["raw_html"]
    assert "<h2>Battery limits</h2>" in task_payload["article"]["raw_html"]


def test_reuse_existing_task_is_scoped_by_access_tier(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    standard_token = issue_standard_token(client)
    vip_token = issue_token(client)
    standard_bearer = {"Authorization": f"Bearer {standard_token['access_token']}"}
    vip_bearer = {"Authorization": f"Bearer {vip_token['access_token']}"}

    standard_response = client.post(
        "/api/tasks",
        headers=standard_bearer,
        json={
            "category": "seo",
            "keyword": "same keyword tier split",
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert standard_response.status_code == 200
    standard_task_id = standard_response.json()["data"]["task_id"]
    wait_for_task_completion(client, standard_bearer, standard_task_id)

    vip_response = client.post(
        "/api/tasks",
        headers=vip_bearer,
        json={
            "category": "seo",
            "keyword": "same keyword tier split",
            "info": "Brand: VoltGo",
            "force_refresh": False,
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert vip_response.status_code == 200
    assert vip_response.json()["data"]["task_id"] != standard_task_id


def test_list_tasks_returns_recent_entries_in_desc_order(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    first_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "first recent task",
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert first_response.status_code == 200
    first_task_id = first_response.json()["data"]["task_id"]
    wait_for_task_completion(client, bearer, first_task_id)

    second_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "geo",
            "keyword": "second recent task",
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert second_response.status_code == 200
    second_task_id = second_response.json()["data"]["task_id"]
    wait_for_task_completion(client, bearer, second_task_id)

    response = client.get("/api/tasks?limit=10", headers=bearer)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    tasks = payload["data"]["tasks"]
    assert [task["task_id"] for task in tasks[:2]] == [second_task_id, first_task_id]
    assert tasks[0]["article_title"]
    assert tasks[0]["progress"]["total"] == 1
    assert tasks[0]["status"] == "completed"


def test_generate_outline_returns_outline_suggestions_and_links(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    response = client.post(
        "/api/outline",
        headers=bearer,
        json={
            "category": "geo",
            "keyword": "Welke thuisbatterij heeft de beste app",
            "info": "Brand: Anker SOLIX. Focus on app experience and household battery comparison.",
            "language": "Dutch",
            "word_limit": 900,
            "task_context": {
                "country": "nl",
                "requires_shopify_link": True,
                "shopify_url": "https://www.ankersolix.com/nl/products/a17c5",
                "ai_qa_content": "AI answer: the best battery app should show live usage, backup status, and tariff insights.",
                "ai_qa_source": "https://www.ankersolix.com/nl/blogs/home-energy",
                "internal_links": [
                    {
                        "label": "Plug-and-play thuisbatterij",
                        "url": "https://www.ankersolix.com/nl/plug-and-play-thuisbatterij/thuisbatterij-a17e2?ref=naviMenu_4_copy",
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    accepted = payload["data"]
    assert accepted["mode_type"] == 3

    data = wait_for_outline_completion(client, bearer, accepted["outline_id"])
    assert data["status"] == "completed"
    assert data["provider"] == "openai:gpt-4.1-mini"
    assert data["word_limit"] == 900
    assert data["outline"]["generation_mode"] == "mock"
    assert "Quick Answer" in data["outline"]["outline_markdown"]
    assert "## Welke oplossing past het best bij welke situatie?" not in data["outline"]["outline_markdown"]
    assert "### Veelgestelde vraag 3" not in data["outline"]["outline_markdown"]
    assert len(data["outline"]["writing_suggestions"]) >= 3
    assert len(data["outline"]["recommended_internal_links"]) >= 2
    assert data["outline"]["recommended_internal_links"][0]["url"].startswith("https://www.ankersolix.com/nl")
    assert data["task_context"]["country"] == "nl"
    assert "tariff insights" in data["task_context"]["ai_qa_content"]
    assert data["task_context"]["ai_qa_source"].startswith("https://www.ankersolix.com")

    longer_response = client.post(
        "/api/outline",
        headers=bearer,
        json={
            "category": "geo",
            "keyword": "Welke thuisbatterij heeft de beste app",
            "info": "Brand: Anker SOLIX. Focus on app experience and household battery comparison.",
            "language": "Dutch",
            "word_limit": 1800,
            "force_refresh": False,
            "task_context": {
                "country": "nl",
                "requires_shopify_link": True,
                "shopify_url": "https://www.ankersolix.com/nl/products/a17c5",
            },
        },
    )
    assert longer_response.status_code == 200
    assert longer_response.json()["data"]["outline_id"] != accepted["outline_id"]
    longer_data = wait_for_outline_completion(client, bearer, longer_response.json()["data"]["outline_id"])
    assert longer_data["word_limit"] == 1800
    assert "## Welke oplossing past het best bij welke situatie?" in longer_data["outline"]["outline_markdown"]
    assert "### Veelgestelde vraag 3" in longer_data["outline"]["outline_markdown"]


def test_export_task_docx_returns_formatted_word_file(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    create_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "portable charger on plane",
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["task_id"]
    wait_for_task_completion(client, bearer, task_id)

    export_response = client.get(f"/api/tasks/{task_id}/export.docx", headers=bearer)
    assert export_response.status_code == 200
    assert (
        export_response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ".docx" in export_response.headers["content-disposition"]

    with zipfile.ZipFile(BytesIO(export_response.content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    assert "Title:" in document_xml
    assert "URL:" in document_xml
    assert "Outline Summary:" in document_xml
    assert "Meta Title:" in document_xml
    assert "Meta Description:" in document_xml
    assert "portable charger on plane" in document_xml.lower()
    assert "Heading1" in document_xml
    assert "Heading2" in document_xml


def test_task_context_changes_cache_scope_and_adds_disclaimer(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}

    de_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "solar rebate guide",
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
            "task_context": {
                "country": "de",
                "article_type": "policy_incentive",
                "requires_shopify_link": True,
                "shopify_url": "https://de.ecoflow.com/products/stream-microinverter",
            },
        },
    )
    au_response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "solar rebate guide",
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
            "task_context": {
                "country": "nl",
                "article_type": "natural_disaster",
            },
        },
    )

    assert de_response.status_code == 200
    assert au_response.status_code == 200
    assert de_response.json()["data"]["task_id"] != au_response.json()["data"]["task_id"]

    de_task = wait_for_task_completion(client, bearer, de_response.json()["data"]["task_id"])
    assert "Disclaimer" in de_task["article"]["raw_html"]
    assert de_task["article"]["audit"]["context"]["country"] == "de"

    limited = client.get("/api/tasks?limit=1", headers=bearer)
    assert limited.status_code == 200
    limited_tasks = limited.json()["data"]["tasks"]
    assert len(limited_tasks) == 1
    assert limited_tasks[0]["task_id"] == au_response.json()["data"]["task_id"]


def test_index_renders_token_and_task_console(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200

    html = response.text
    assert "Exchange Token" in html
    assert "Get 1-Day Token" in html
    assert "content_image_count" in html
    assert "mode_type" in html
    assert "ai_qa_content" in html
    assert "AI Q&A Content" in html
    assert "Keyword / Outline" in html
    assert "/api/tasks" in html
    assert "/api/token" in html
    assert "Recent Tasks" in html
    assert "Outline Demo" in html


def test_outline_page_renders_outline_console(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)

    response = client.get("/outline")
    assert response.status_code == 200

    html = response.text
    assert "SEO / GEO Outline Writer" in html
    assert "Info" in html
    assert "Requires Shopify Link" in html
    assert "Shopify URL" in html
    assert "AI Q&A Content" in html
    assert "ai_qa_source" in html
    assert "/api/outline" in html
    assert "/api/outline/{outline_id}" in html
    assert "Article Demo" in html


def test_openapi_only_exposes_task_endpoints(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)

    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths.keys()) == {
        "/api/token",
        "/api/outline",
        "/api/outline/{outline_id}",
        "/api/tasks",
        "/api/tasks/{task_id}",
        "/api/tasks/{task_id}/export.docx",
    }


def test_openapi_exposes_bearer_security_scheme(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)

    response = client.get("/openapi.json")
    assert response.status_code == 200
    components = response.json()["components"]["securitySchemes"]
    assert "HTTPBearer" in components
    assert components["HTTPBearer"]["type"] == "http"
    assert components["HTTPBearer"]["scheme"] == "bearer"


def test_create_task_returns_json_when_service_fails(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}
    app.state.services.task_service.create_task = lambda **_: (_ for _ in ()).throw(RuntimeError("db down"))

    response = client.post(
        "/api/tasks",
        headers=bearer,
        json={
            "category": "seo",
            "keyword": "best usb c charger",
            "info": "Brand: VoltGo",
        },
    )
    assert response.status_code == 503
    payload = response.json()
    assert payload["success"] is False
    assert payload["message"] == "task service is temporarily unavailable"


def test_get_task_returns_json_when_service_fails(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
            "normal_access_key": "test-standard-key",
            "vip_access_key": "test-vip-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)
    token_data = issue_token(client)
    bearer = {"Authorization": f"Bearer {token_data['access_token']}"}
    app.state.services.task_service.get_task = lambda *_: (_ for _ in ()).throw(RuntimeError("db down"))

    response = client.get("/api/tasks/1", headers=bearer)
    assert response.status_code == 503
    payload = response.json()
    assert payload["success"] is False
    assert payload["message"] == "task service is temporarily unavailable"
    assert payload["status"] == "error"
