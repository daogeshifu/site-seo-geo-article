from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.templating import Jinja2Templates

from app.core.config import Settings
from app.services.auth_service import AuthService
from app.services.cache_service import CacheService
from app.services.image_service import ImageService
from app.services.llm_client import LLMClient
from app.services.oss_service import AliyunOSSService
from app.services.task_repository import TaskRepository, build_task_repository
from app.services.task_service import TaskService
from app.services.writer_service import WriterService


@dataclass
class AppServices:
    settings: Settings
    auth_service: AuthService
    cache_service: CacheService
    image_service: ImageService
    writer_service: WriterService
    task_repository: TaskRepository
    task_service: TaskService
    templates: Jinja2Templates


def build_services(config_override: dict[str, Any] | None = None) -> AppServices:
    app_root = Path(__file__).resolve().parent.parent
    settings = Settings.from_env()
    if config_override:
        for key, value in config_override.items():
            setattr(settings, key, value)
        settings.cache_dir = settings.data_dir / "cache"
        settings.image_dir = settings.data_dir / "images"

    cache_service = CacheService(settings.cache_dir)
    auth_service = AuthService(settings)
    oss_service = AliyunOSSService(settings)
    image_service = ImageService(settings, oss_service=oss_service)
    writer_service = WriterService(LLMClient(settings), image_service=image_service)
    task_repository = build_task_repository(settings)
    task_service = TaskService(
        writer_service=writer_service,
        cache_service=cache_service,
        task_repository=task_repository,
        max_workers=settings.max_workers,
    )

    return AppServices(
        settings=settings,
        auth_service=auth_service,
        cache_service=cache_service,
        image_service=image_service,
        writer_service=writer_service,
        task_repository=task_repository,
        task_service=task_service,
        templates=Jinja2Templates(directory=str(app_root / "web" / "templates")),
    )
