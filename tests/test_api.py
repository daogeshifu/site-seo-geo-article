import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.factory import create_app


def issue_token(client: TestClient) -> dict:
    response = client.post("/api/token", json={"access_key": "test-vip-key"})
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
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["task_id"]
    assert create_response.json()["data"]["access_tier"] == "vip"

    task_payload = wait_for_task_completion(client, bearer, task_id)
    status = task_payload["status"]
    assert status == "completed"
    assert task_payload is not None
    assert task_payload["access_tier"] == "vip"
    assert task_payload["keyword"] == "portable charger on plane"
    assert task_payload["word_limit"] == 1200
    assert task_payload["article"]["generation_mode"] == "mock"
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
    assert "/api/tasks" in html
    assert "/api/token" in html


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
    assert set(paths.keys()) == {"/api/token", "/api/tasks", "/api/tasks/{task_id}"}


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
