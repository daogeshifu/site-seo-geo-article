from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.services.cache_service import CacheService
from app.services.task_repository import TaskRepository
from app.services.writer_service import WriterService
from app.utils.common import normalize_text, utcnow_iso


FINAL_STATUSES = {"completed", "failed"}


class TaskService:
    def __init__(
        self,
        *,
        writer_service: WriterService,
        cache_service: CacheService,
        task_repository: TaskRepository,
        max_workers: int = 2,
    ) -> None:
        self.writer_service = writer_service
        self.cache_service = cache_service
        self.task_repository = task_repository
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="article-task")

    def create_task(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        language: str = "English",
        word_limit: int = 1200,
        force_refresh: bool = False,
        include_cover: int = 1,
        content_image_count: int = 3,
        access_tier: str = "standard",
    ) -> dict[str, Any]:
        normalized_category = normalize_text(category)
        normalized_keyword = keyword.strip()
        normalized_language = (language or "English").strip() or "English"
        normalized_info = info or ""
        normalized_word_limit = max(200, min(10000, int(word_limit)))

        if not normalized_keyword:
            raise ValueError("A keyword is required.")

        if not force_refresh:
            reusable_task = self.task_repository.find_reusable_task(
                category=normalized_category,
                keyword=normalized_keyword,
                info=normalized_info,
                language=normalized_language,
                word_limit=normalized_word_limit,
            )
            if reusable_task:
                return self.get_task(int(reusable_task["task_id"])) or reusable_task

        task = self.task_repository.create_task(
            {
                "category": normalized_category,
                "keyword": normalized_keyword,
                "info": normalized_info,
                "language": normalized_language,
                "word_limit": normalized_word_limit,
                "force_refresh": bool(force_refresh),
                "include_cover": max(0, min(1, int(include_cover))),
                "content_image_count": max(0, min(3, int(content_image_count))),
                "access_tier": access_tier,
                "cache_key": self.cache_service.build_key(
                    normalized_category,
                    normalized_keyword,
                    normalized_info,
                    normalized_word_limit,
                ),
                "status": "queued",
            }
        )
        self.executor.submit(self._run_task, int(task["task_id"]))
        return self.get_task(int(task["task_id"])) or task

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        task = self.task_repository.get_task(int(task_id))
        if not task:
            return None

        payload = dict(task)
        result = self.task_repository.get_result(int(task_id))
        if result:
            payload["article"] = self.writer_service.present_article(
                asset_namespace=payload["cache_key"],
                article=result["article"],
                include_cover=payload.get("include_cover", 1),
                content_image_count=payload.get("content_image_count", 3),
            )
        else:
            payload["article"] = None

        payload["progress"] = {
            "total": 1,
            "completed": 1 if payload["status"] == "completed" else 0,
            "failed": 1 if payload["status"] == "failed" else 0,
            "cached": 1 if payload["cache_hit"] else 0,
        }
        return payload

    def _run_task(self, task_id: int) -> None:
        task = self.task_repository.get_task(task_id)
        if not task:
            return

        self.task_repository.update_task(task_id, status="running", error_message=None)
        task = self.task_repository.get_task(task_id)
        if not task:
            return

        try:
            cached = None
            if not task["force_refresh"]:
                cached = self.cache_service.get(
                    task["category"],
                    task["keyword"],
                    task["info"],
                    task.get("word_limit", 1200),
                )

            if cached:
                article = cached["article"]
                needs_images = task.get("include_cover", 1) > 0 or task.get("content_image_count", 0) > 0
                if needs_images:
                    article = self.writer_service.ensure_images(
                        asset_namespace=task["cache_key"],
                        article=article,
                        category=task["category"],
                        keyword=task["keyword"],
                        info=task["info"],
                        include_cover=task.get("include_cover", 1),
                        content_image_count=task.get("content_image_count", 0),
                    )
                    self.cache_service.set(
                        task["category"],
                        task["keyword"],
                        task["info"],
                        article,
                        task.get("word_limit", 1200),
                    )
                cache_hit = True
            else:
                article = self.writer_service.generate(
                    asset_namespace=task["cache_key"],
                    category=task["category"],
                    keyword=task["keyword"],
                    info=task["info"],
                    language=task["language"],
                    word_limit=task.get("word_limit", 1200),
                    include_cover=task.get("include_cover", 1),
                    content_image_count=task.get("content_image_count", 0),
                )
                self.cache_service.set(
                    task["category"],
                    task["keyword"],
                    task["info"],
                    article,
                    task.get("word_limit", 1200),
                )
                cache_hit = False

            self.task_repository.save_result(task_id, article)
            self.task_repository.update_task(
                task_id,
                status="completed",
                cache_hit=cache_hit,
                error_message=None,
                completed_at=utcnow_iso(),
            )
        except Exception as exc:
            self.task_repository.update_task(
                task_id,
                status="failed",
                cache_hit=False,
                error_message=str(exc),
                completed_at=utcnow_iso(),
            )
