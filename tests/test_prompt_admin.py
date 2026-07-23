from pathlib import Path

from fastapi.testclient import TestClient

from app.core.factory import create_app
from app.services.prompt_builder import build_polish_prompt, build_strategy_prompt


def build_client(tmp_path: Path, admin_password: str = "test-admin-password") -> TestClient:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "admin_password": admin_password,
            "token_signing_secret": "test-signing-secret",
        }
    )
    return TestClient(app)


def login(client: TestClient, password: str = "test-admin-password") -> None:
    response = client.post("/admin/login", data={"password": password}, follow_redirects=False)
    assert response.status_code == 303


def test_console_requires_login(tmp_path: Path) -> None:
    client = build_client(tmp_path)

    assert client.get("/admin/api/prompts").status_code == 401
    assert client.post("/admin/login", data={"password": "wrong"}).status_code == 401

    login(client)
    payload = client.get("/admin/api/prompts").json()
    assert payload["success"] is True
    assert any(item["key"] == "strategy.seo" for item in payload["data"]["items"])


def test_saved_prompt_changes_generated_prompt(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    login(client)

    response = client.put(
        "/admin/api/prompts/strategy.seo",
        json={"text": "Custom strategy prompt for {{keyword}} in {{language}}.\n{{mode_context}}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["customized"] is True

    prompt = build_strategy_prompt("seo", "solar battery", "Brand: VoltGo", "English", {}, 1200)
    assert prompt.startswith("Custom strategy prompt for")
    assert "Keyword:\nsolar battery" in prompt
    assert (tmp_path / "prompts.json").exists()

    reset = client.post("/admin/api/prompts/strategy.seo/reset")
    assert reset.status_code == 200
    assert reset.json()["data"]["customized"] is False
    assert "You are a senior SEO content strategist." in build_strategy_prompt(
        "seo", "solar battery", "", "English", {}, 1200
    )


def test_shared_fragment_edit_reaches_every_stage(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    login(client)

    client.put("/admin/api/prompts/shared.cta.base", json={"text": "CTA rule: keep it short."})

    assert "CTA rule: keep it short." in build_strategy_prompt("geo", "kw", "", "English", {}, 1200)
    assert "CTA rule: keep it short." in build_polish_prompt("geo", "English", "kw", "<h1>x</h1>", {}, 1200)


def test_invalid_updates_are_rejected(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    login(client)

    assert client.put("/admin/api/prompts/does.not.exist", json={"text": "x"}).status_code == 404
    assert client.put("/admin/api/prompts/strategy.seo", json={"text": "   "}).status_code == 400


def test_preview_returns_assembled_prompt(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    login(client)

    response = client.post(
        "/admin/api/preview",
        json={"stage": "outline", "category": "geo", "keyword": "home battery", "word_limit": 1200},
    )
    assert response.status_code == 200
    prompt = response.json()["data"]["prompt"]
    assert "You are a senior GEO content strategist." in prompt
    assert "home battery" in prompt


def test_console_disabled_without_password(tmp_path: Path) -> None:
    client = build_client(tmp_path, admin_password="")

    assert "ADMIN_PASSWORD" in client.get("/admin").text
    assert client.get("/admin/api/prompts").status_code == 503


def test_access_key_is_not_accepted_as_admin_password(tmp_path: Path) -> None:
    app = create_app(
        {
            "data_dir": tmp_path,
            "llm_mock_mode": True,
            "admin_password": "test-admin-password",
            "vip_access_key": "test-vip-key",
            "normal_access_key": "test-standard-key",
            "token_signing_secret": "test-signing-secret",
        }
    )
    client = TestClient(app)

    assert client.post("/admin/login", data={"password": "test-vip-key"}).status_code == 401
    assert client.post("/admin/login", data={"password": "test-standard-key"}).status_code == 401
    login(client)


def test_backup_restore_and_delete(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    login(client)

    client.put("/admin/api/prompts/polish.flavor.seo", json={"text": "Version one."})
    created = client.post("/admin/api/backups", json={"note": "基线"})
    assert created.status_code == 200
    backup_id = created.json()["data"]["id"]
    assert created.json()["data"]["customized_count"] == 1

    client.put("/admin/api/prompts/polish.flavor.seo", json={"text": "Version two."})
    client.put("/admin/api/prompts/polish.flavor.geo", json={"text": "Extra edit."})
    assert "Version two." in build_polish_prompt("seo", "English", "kw", "<h1>x</h1>", {}, 1200)

    restored = client.post(f"/admin/api/backups/{backup_id}/restore")
    assert restored.status_code == 200
    assert "Version one." in build_polish_prompt("seo", "English", "kw", "<h1>x</h1>", {}, 1200)
    assert "Extra edit." not in build_polish_prompt("geo", "English", "kw", "<h1>x</h1>", {}, 1200)

    items = client.get("/admin/api/backups").json()["data"]["items"]
    assert [item["id"] for item in items][0] != backup_id, "restore should snapshot the pre-restore state first"
    assert any(item["note"] == "基线" for item in items)

    assert client.delete(f"/admin/api/backups/{backup_id}").status_code == 200
    assert all(item["id"] != backup_id for item in client.get("/admin/api/backups").json()["data"]["items"])


def test_backup_id_is_validated(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    login(client)

    assert client.post("/admin/api/backups/..%2F..%2Fetc/restore").status_code == 404
    assert client.delete("/admin/api/backups/not-an-id").status_code == 404
