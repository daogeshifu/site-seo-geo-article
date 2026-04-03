import time
from pathlib import Path

from seo_geo_writer.web import create_app


def test_create_task_and_fetch_result(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "openai_api_key": "",
        }
    )
    client = app.test_client()

    create_response = client.post(
        "/api/tasks",
        json={
            "category": "geo",
            "keywords": ["portable charger on plane"],
            "info": "Brand: VoltGo",
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.get_json()["data"]["task_id"]

    deadline = time.time() + 5
    status = None
    task_payload = None
    while time.time() < deadline:
        task_response = client.get(f"/api/tasks/{task_id}")
        assert task_response.status_code == 200
        task_payload = task_response.get_json()["data"]
        status = task_payload["status"]
        if status in {"completed", "failed", "partial_failed"}:
            break
        time.sleep(0.1)

    assert status == "completed"
    assert task_payload is not None
    assert task_payload["items"][0]["article"]["generation_mode"] == "mock"
