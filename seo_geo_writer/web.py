from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from demo import render_demo_page
from .cache_service import CacheService
from .config import Settings
from .image_service import ImageService
from .llm_client import LLMClient
from .task_service import TaskService
from .utils import split_keywords
from .writer_service import WriterService


def create_app(config_override: dict[str, Any] | None = None) -> Flask:
    root_path = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(root_path / "templates"),
        static_folder=str(root_path / "static"),
    )

    settings = Settings.from_env()
    if config_override:
        for key, value in config_override.items():
            setattr(settings, key, value)
        settings.cache_dir = settings.data_dir / "cache"
        settings.tasks_dir = settings.data_dir / "tasks"
        settings.image_dir = settings.data_dir / "images"

    cache_service = CacheService(settings.cache_dir)
    image_service = ImageService(settings)
    writer_service = WriterService(LLMClient(settings), image_service=image_service)
    task_service = TaskService(
        writer_service=writer_service,
        cache_service=cache_service,
        tasks_dir=settings.tasks_dir,
        max_workers=settings.max_workers,
    )

    app.config.update(
        HOST=settings.host,
        PORT=settings.port,
        DEBUG=settings.debug,
        SETTINGS=settings,
        TASK_SERVICE=task_service,
    )

    @app.get("/")
    def index() -> str:
        return render_demo_page(
            llm_enabled=writer_service.llm_client.enabled,
            image_enabled=image_service.enabled,
            image_mode=image_service.mode,
        )

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "success": True,
                "data": {
                    "status": "ok",
                    "llm_enabled": writer_service.llm_client.enabled,
                    "mock_mode": not writer_service.llm_client.enabled,
                    "image_generation_enabled": image_service.enabled,
                    "image_generation_mode": image_service.mode,
                },
            }
        )

    @app.get("/generated/<asset_namespace>/<path:filename>")
    def serve_generated_asset(asset_namespace: str, filename: str):
        directory = settings.image_dir / asset_namespace
        return send_from_directory(directory, filename)

    @app.post("/api/tasks")
    def create_task():
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        category = str(payload.get("category", "")).strip().lower()
        info = str(payload.get("info", payload.get("brand_info", ""))).strip()
        language = str(payload.get("language", "English")).strip() or "English"
        force_refresh = str(payload.get("force_refresh", "false")).lower() in {"1", "true", "yes"}
        generate_images = str(payload.get("generate_images", "true")).lower() in {"1", "true", "yes"}

        if category not in {"seo", "geo"}:
            return jsonify({"success": False, "message": "category must be seo or geo"}), 400

        keywords = split_keywords(payload.get("keywords", ""))
        if not keywords:
            return jsonify({"success": False, "message": "keywords is required"}), 400

        task = task_service.create_task(
            category=category,
            keywords=keywords,
            info=info,
            language=language,
            force_refresh=force_refresh,
            generate_images=generate_images,
        )
        return jsonify(
            {
                "success": True,
                "data": {
                    "task_id": task["task_id"],
                    "status": task["status"],
                },
            }
        )

    @app.get("/api/tasks/<task_id>")
    def get_task(task_id: str):
        task = task_service.get_task(task_id)
        if not task:
            return jsonify({"success": False, "message": "task not found"}), 404
        return jsonify({"success": True, "data": task})

    return app
