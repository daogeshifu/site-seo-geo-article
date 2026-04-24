from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.services.outline_service import OutlineService
from app.services.task_modes import MODE_TYPE_OUTLINE_TASK
from app.services.task_repository import TaskRepository
from app.utils.common import utcnow_iso


FINAL_STATUSES = {"completed", "failed"}
OUTLINE_WORD_LIMIT = 1200


class OutlineTaskService:
    def __init__(
        self,
        *,
        outline_service: OutlineService,
        task_repository: TaskRepository,
        max_workers: int = 2,
    ) -> None:
        self.outline_service = outline_service
        self.task_repository = task_repository
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="outline-task")

    def create_task(
        self,
        *,
        category: str,
        keyword: str,
        info: str,
        task_context: dict[str, Any] | None = None,
        language: str = "English",
        provider: str = "openai",
        force_refresh: bool = False,
        access_tier: str = "standard",
    ) -> dict[str, Any]:
        normalized_category = (category or "").strip().lower()
        normalized_keyword = keyword.strip()
        normalized_info = info or ""
        normalized_task_context = self.outline_service.rulebook_service.normalize_task_context(task_context)
        normalized_language = (language or "English").strip() or "English"
        normalized_provider = (provider or "openai").strip().lower() or "openai"
        normalized_access_tier = (access_tier or "standard").strip().lower() or "standard"

        if not normalized_keyword:
            raise ValueError("A keyword is required.")

        if not force_refresh:
            reusable_task = self.task_repository.find_reusable_task(
                category=normalized_category,
                keyword=normalized_keyword,
                mode_type=MODE_TYPE_OUTLINE_TASK,
                info=normalized_info,
                task_context=normalized_task_context,
                language=normalized_language,
                word_limit=OUTLINE_WORD_LIMIT,
                access_tier=normalized_access_tier,
                provider=normalized_provider,
            )
            if reusable_task:
                return self.get_task(int(reusable_task["task_id"])) or reusable_task

        task = self.task_repository.create_task(
            {
                "category": normalized_category,
                "keyword": normalized_keyword,
                "mode_type": MODE_TYPE_OUTLINE_TASK,
                "info": normalized_info,
                "task_context": normalized_task_context,
                "language": normalized_language,
                "provider": normalized_provider,
                "word_limit": OUTLINE_WORD_LIMIT,
                "force_refresh": bool(force_refresh),
                "include_cover": 0,
                "content_image_count": 0,
                "access_tier": normalized_access_tier,
                "cache_key": "",
                "status": "queued",
            }
        )
        self.executor.submit(self._run_task, int(task["task_id"]))
        return self.get_task(int(task["task_id"])) or task

    def get_task(self, outline_id: int) -> dict[str, Any] | None:
        task = self.task_repository.get_task(int(outline_id))
        if not task or int(task.get("mode_type", 0)) != MODE_TYPE_OUTLINE_TASK:
            return None

        payload = self._build_task_summary(task)
        result = self.task_repository.get_result(int(outline_id))
        payload["outline"] = result["article"] if result else None
        return payload

    def _run_task(self, outline_id: int) -> None:
        task = self.task_repository.get_task(outline_id)
        if not task or int(task.get("mode_type", 0)) != MODE_TYPE_OUTLINE_TASK:
            return

        self.task_repository.update_task(outline_id, status="running", error_message=None)
        task = self.task_repository.get_task(outline_id)
        if not task:
            return

        try:
            outline = self.outline_service.generate(
                category=task["category"],
                keyword=task["keyword"],
                info=task.get("info", ""),
                task_context=task.get("task_context") or {},
                language=task.get("language", "English"),
                provider=task.get("provider", "openai"),
                access_tier=task.get("access_tier", "standard"),
            )
            self.task_repository.save_result(outline_id, outline)
            self.task_repository.update_task(
                outline_id,
                status="completed",
                cache_hit=False,
                error_message=None,
                completed_at=utcnow_iso(),
            )
        except Exception as exc:
            self.task_repository.update_task(
                outline_id,
                status="failed",
                cache_hit=False,
                error_message=str(exc),
                completed_at=utcnow_iso(),
            )

    @staticmethod
    def _build_task_summary(task: dict[str, Any]) -> dict[str, Any]:
        payload = dict(task)
        payload["outline_id"] = payload["task_id"]
        payload["progress"] = {
            "total": 1,
            "completed": 1 if payload["status"] == "completed" else 0,
            "failed": 1 if payload["status"] == "failed" else 0,
            "cached": 1 if payload["cache_hit"] else 0,
        }
        return payload
