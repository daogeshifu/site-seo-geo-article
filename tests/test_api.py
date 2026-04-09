import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.factory import create_app


def issue_token(client: TestClient) -> dict:
    response = client.post("/api/token", json={"access_key": "test-vip-key"})
    assert response.status_code == 200
    return response.json()["data"]


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
            "keywords": ["portable charger on plane"],
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
            "keywords": ["portable charger on plane"],
            "info": "Brand: VoltGo",
            "include_cover": 1,
            "content_image_count": 2,
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["task_id"]
    assert create_response.json()["data"]["access_tier"] == "vip"

    deadline = time.time() + 5
    status = None
    task_payload = None
    while time.time() < deadline:
        task_response = client.get(f"/api/tasks/{task_id}", headers=bearer)
        assert task_response.status_code == 200
        task_payload = task_response.json()["data"]
        status = task_payload["status"]
        if status in {"completed", "failed", "partial_failed"}:
            break
        time.sleep(0.1)

    assert status == "completed"
    assert task_payload is not None
    assert task_payload["access_tier"] == "vip"
    assert task_payload["items"][0]["article"]["generation_mode"] == "mock"
    assert len(task_payload["items"][0]["article"]["images"]) == 3
    assert task_payload["items"][0]["article"]["cover_image"] is not None
    assert len(task_payload["items"][0]["article"]["content_images"]) == 2
    assert task_payload["items"][0]["article"]["images"][0]["data_url"].startswith("data:image/")


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
            "keywords": ["best usb c charger"],
            "info": "Brand: VoltGo",
            "include_cover": 0,
            "content_image_count": 0,
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["task_id"]

    deadline = time.time() + 5
    while time.time() < deadline:
        task_response = client.get(f"/api/tasks/{task_id}", headers=bearer)
        assert task_response.status_code == 200
        task_payload = task_response.json()["data"]
        if task_payload["status"] in {"completed", "failed", "partial_failed"}:
            break
        time.sleep(0.1)

    article = task_payload["items"][0]["article"]
    assert article["images"] == []
    assert article["cover_image"] is None
    assert article["content_images"] == []
    assert article["image_generation_mode"] == "disabled"


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
    assert set(paths.keys()) == {"/api/tasks", "/api/tasks/{task_id}"}
