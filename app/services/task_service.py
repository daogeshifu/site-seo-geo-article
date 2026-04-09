from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Any

from app.services.cache_service import CacheService
from app.services.writer_service import WriterService
from app.utils.common import atomic_write_json, ensure_dir, load_json, split_keywords, utcnow_iso


FINAL_STATUSES = {"completed", "failed", "partial_failed"}


class TaskService:
    def __init__(
        self,
        *,
        writer_service: WriterService,
        cache_service: CacheService,
        tasks_dir: Path,
        max_workers: int = 2,
    ) -> None:
        self.writer_service = writer_service
        self.cache_service = cache_service
        self.tasks_dir = tasks_dir
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="article-task")
        self._lock = Lock()
        self._tasks: dict[str, dict[str, Any]] = {}
        ensure_dir(tasks_dir)
        self._load_existing_tasks()

    def _load_existing_tasks(self) -> None:
        for path in sorted(self.tasks_dir.glob("*.json")):
            try:
                payload = load_json(path)
                self._tasks[payload["task_id"]] = payload
            except Exception:
                continue

    def _task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def _save_task(self, task: dict[str, Any]) -> None:
        task["updated_at"] = utcnow_iso()
        self._tasks[task["task_id"]] = task
        atomic_write_json(self._task_path(task["task_id"]), task)

    def create_task(
        self,
        *,
        category: str,
        keywords: list[str] | str,
        info: str,
        language: str = "English",
        force_refresh: bool = False,
        include_cover: int = 1,
        content_image_count: int = 3,
        access_tier: str = "standard",
    ) -> dict[str, Any]:
        keyword_list = split_keywords(keywords)
        if not keyword_list:
            raise ValueError("At least one keyword is required.")

        task_id = uuid.uuid4().hex
        now = utcnow_iso()
        task = {
            "task_id": task_id,
            "category": category,
            "keywords": keyword_list,
            "info": info,
            "language": language,
            "force_refresh": force_refresh,
            "include_cover": max(0, min(1, int(include_cover))),
            "content_image_count": max(0, min(3, int(content_image_count))),
            "access_tier": access_tier,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "items": [
                {
                    "keyword": keyword,
                    "cache_key": self.cache_service.build_key(category, keyword, info),
                    "status": "pending",
                    "cache_hit": False,
                    "article": None,
                    "error": None,
                }
                for keyword in keyword_list
            ],
        }

        with self._lock:
            self._save_task(task)

        self.executor.submit(self._run_task, task_id)
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if not task:
            path = self._task_path(task_id)
            if not path.exists():
                return None
            task = load_json(path)
            self._tasks[task_id] = task
        return self._build_response_payload(task)

    def _compute_progress(self, items: list[dict[str, Any]]) -> dict[str, int]:
        completed = sum(1 for item in items if item["status"] == "completed")
        failed = sum(1 for item in items if item["status"] == "failed")
        cached = sum(1 for item in items if item["cache_hit"])
        return {
            "total": len(items),
            "completed": completed,
            "failed": failed,
            "cached": cached,
        }

    def _build_response_payload(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(task)
        for item in payload["items"]:
            if item.get("article"):
                item["article"] = self.writer_service.present_article(
                    asset_namespace=item["cache_key"],
                    article=item["article"],
                    include_cover=payload.get("include_cover", 1),
                    content_image_count=payload.get("content_image_count", 3),
                )
        payload["progress"] = self._compute_progress(payload["items"])
        return payload

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            task = deepcopy(self._tasks[task_id])
            task["status"] = "running"
            self._save_task(task)

        for item in task["items"]:
            keyword = item["keyword"]
            cache_key = item["cache_key"]
            try:
                cached = None
                if not task["force_refresh"]:
                    cached = self.cache_service.get(task["category"], keyword, task["info"])

                if cached:
                    article = cached["article"]
                    needs_images = (
                        task.get("include_cover", 1) > 0 or task.get("content_image_count", 3) > 0
                    )
                    if needs_images:
                        article = self.writer_service.ensure_images(
                            asset_namespace=cache_key,
                            article=article,
                            category=task["category"],
                            keyword=keyword,
                            info=task["info"],
                            include_cover=task.get("include_cover", 1),
                            content_image_count=task.get("content_image_count", 3),
                        )
                        self.cache_service.set(task["category"], keyword, task["info"], article)
                    item["status"] = "completed"
                    item["cache_hit"] = True
                    item["article"] = article
                    item["error"] = None
                else:
                    item["status"] = "running"
                    with self._lock:
                        self._save_task(task)

                    article = self.writer_service.generate(
                        asset_namespace=cache_key,
                        category=task["category"],
                        keyword=keyword,
                        info=task["info"],
                        language=task["language"],
                        include_cover=task.get("include_cover", 1),
                        content_image_count=task.get("content_image_count", 3),
                    )
                    self.cache_service.set(task["category"], keyword, task["info"], article)
                    item["status"] = "completed"
                    item["cache_hit"] = False
                    item["article"] = article
                    item["error"] = None
            except Exception as exc:
                item["status"] = "failed"
                item["error"] = str(exc)

            with self._lock:
                self._save_task(task)

        failed_count = sum(1 for item in task["items"] if item["status"] == "failed")
        if failed_count == len(task["items"]):
            task["status"] = "failed"
        elif failed_count > 0:
            task["status"] = "partial_failed"
        else:
            task["status"] = "completed"

        with self._lock:
            self._save_task(task)
