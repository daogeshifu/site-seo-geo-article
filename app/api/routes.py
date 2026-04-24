from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.runtime import AppServices
from app.services.task_modes import ARTICLE_MODE_TYPES, MODE_TYPE_OUTLINE_TASK
from app.services.task_service import FINAL_STATUSES
from .schemas import (
    ErrorResponse,
    OutlineCreateRequest,
    OutlineCreateResponse,
    OutlineData,
    OutlineDetailResponse,
    TaskAcceptedData,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskDetailResponse,
    TaskListData,
    TaskListResponse,
    TokenExchangeData,
    TokenExchangeRequest,
    TokenExchangeResponse,
)

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def resolve_auth_payload(
    services: AppServices,
    authorization: HTTPAuthorizationCredentials | None,
) -> dict[str, str] | None:
    if not authorization:
        return None
    if authorization.scheme.lower() != "bearer" or not authorization.credentials.strip():
        return None
    return services.auth_service.verify_token(authorization.credentials)


def create_api_router(services: AppServices) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post(
        "/token",
        tags=["auth"],
        response_model=TokenExchangeResponse,
        responses={403: {"model": ErrorResponse}},
        summary="Exchange an access key for a 1-day bearer token",
    )
    async def exchange_token(payload: TokenExchangeRequest) -> TokenExchangeResponse | JSONResponse:
        issued = services.auth_service.issue_token(payload.access_key)
        if not issued:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"success": False, "message": "valid access key is required"},
            )
        return TokenExchangeResponse(data=TokenExchangeData(**issued))

    @router.post(
        "/outline",
        tags=["tasks"],
        response_model=OutlineCreateResponse,
        responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
        summary="Create an async SEO or GEO outline task",
    )
    async def create_outline(
        payload: OutlineCreateRequest,
        authorization: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> OutlineCreateResponse | JSONResponse:
        category = payload.category.strip().lower()
        keyword = payload.keyword.strip()
        info = (payload.info or "").strip()
        language = (payload.language or "English").strip() or "English"
        provider = (payload.provider or "openai").strip().lower()
        task_context = services.writer_service.rulebook_service.normalize_task_context(payload.task_context.model_dump())
        auth_payload = resolve_auth_payload(services, authorization)

        if category not in {"seo", "geo"}:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "category must be seo or geo"},
            )

        if not auth_payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "valid bearer token is required"},
            )

        if not keyword:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "keyword is required"},
            )

        if provider not in {"openai", "anthropic"}:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "provider must be openai or anthropic"},
            )

        try:
            outline = services.outline_task_service.create_task(
                category=category,
                keyword=keyword,
                info=info,
                task_context=task_context,
                language=language,
                provider=provider,
                force_refresh=payload.force_refresh,
                access_tier=auth_payload["tier"],
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": str(exc)},
            )
        except Exception:
            logger.exception("Outline service unavailable while generating an outline.")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"success": False, "message": "outline service is temporarily unavailable"},
            )

        return OutlineCreateResponse(
            data={
                "outline_id": outline["task_id"],
                "status": outline["status"],
                "access_tier": auth_payload["tier"],
                "mode_type": outline.get("mode_type", MODE_TYPE_OUTLINE_TASK),
            }
        )

    @router.get(
        "/outline/{outline_id}",
        tags=["tasks"],
        response_model=OutlineDetailResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        summary="Fetch an async outline task result",
    )
    async def get_outline(
        outline_id: int,
        authorization: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> OutlineDetailResponse | JSONResponse:
        auth_payload = resolve_auth_payload(services, authorization)
        if not auth_payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "valid bearer token is required"},
            )

        try:
            outline = services.outline_task_service.get_task(outline_id)
        except Exception:
            logger.exception("Outline service unavailable while fetching outline_id=%s.", outline_id)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "message": "outline service is temporarily unavailable",
                    "status": "error",
                    "outline_id": outline_id,
                },
            )
        if not outline:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": "outline task not found"},
            )
        if outline.get("status") == "failed":
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": outline.get("error_message") or "outline task failed",
                    "status": "failed",
                    "outline_id": outline_id,
                    "error": outline.get("error_message"),
                },
            )
        if outline.get("status") not in FINAL_STATUSES or not outline.get("outline"):
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": "outline task not completed",
                    "status": outline.get("status", "running"),
                    "outline_id": outline_id,
                },
            )
        return OutlineDetailResponse(data=outline)

    @router.post(
        "/tasks",
        tags=["tasks"],
        response_model=TaskCreateResponse,
        responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
        summary="Create an async article generation task",
    )
    async def create_task(
        payload: TaskCreateRequest,
        authorization: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> TaskCreateResponse | JSONResponse:
        category = payload.category.strip().lower()
        keyword = payload.keyword.strip()
        mode_type = int(payload.mode_type or 1)
        info = (payload.info or payload.brand_info or "").strip()
        language = (payload.language or "English").strip() or "English"
        provider = (payload.provider or "openai").strip().lower()
        task_context = services.writer_service.rulebook_service.normalize_task_context(payload.task_context.model_dump())
        auth_payload = resolve_auth_payload(services, authorization)

        if category not in {"seo", "geo"}:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "category must be seo or geo"},
            )

        if not auth_payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "valid bearer token is required"},
            )

        if not keyword:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "keyword is required"},
            )

        if mode_type not in {1, 2}:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "mode_type must be 1 or 2"},
            )

        if provider not in {"openai", "anthropic"}:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "provider must be openai or anthropic"},
            )

        try:
            task = services.task_service.create_task(
                category=category,
                keyword=keyword,
                mode_type=mode_type,
                info=info,
                task_context=task_context,
                language=language,
                provider=provider,
                word_limit=payload.word_limit,
                force_refresh=payload.force_refresh,
                include_cover=payload.include_cover,
                content_image_count=payload.content_image_count,
                access_tier=auth_payload["tier"],
            )
        except Exception:
            logger.exception("Task service unavailable while creating a task.")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"success": False, "message": "task service is temporarily unavailable"},
            )
        return TaskCreateResponse(
            data=TaskAcceptedData(
                task_id=task["task_id"],
                status=task["status"],
                access_tier=auth_payload["tier"],
                mode_type=task.get("mode_type", mode_type),
            )
        )

    @router.get(
        "/tasks",
        tags=["tasks"],
        response_model=TaskListResponse,
        responses={401: {"model": ErrorResponse}},
        summary="Fetch the latest async tasks",
    )
    async def list_tasks(
        limit: int = Query(default=10, ge=1, le=50),
        authorization: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> TaskListResponse | JSONResponse:
        auth_payload = resolve_auth_payload(services, authorization)
        if not auth_payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "valid bearer token is required"},
            )

        try:
            tasks = services.task_service.list_tasks(limit=limit)
        except Exception:
            logger.exception("Task service unavailable while listing tasks.")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"success": False, "message": "task service is temporarily unavailable"},
            )
        return TaskListResponse(data=TaskListData(tasks=tasks))

    @router.get(
        "/tasks/{task_id}",
        tags=["tasks"],
        response_model=TaskDetailResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        summary="Fetch an async task result",
    )
    async def get_task(
        task_id: int,
        authorization: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> TaskDetailResponse | JSONResponse:
        auth_payload = resolve_auth_payload(services, authorization)
        if not auth_payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "valid bearer token is required"},
            )

        try:
            task = services.task_service.get_task(task_id)
        except Exception:
            logger.exception("Task service unavailable while fetching task_id=%s.", task_id)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "message": "task service is temporarily unavailable",
                    "status": "error",
                    "task_id": task_id,
                },
            )
        if not task:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": "task not found"},
            )
        if int(task.get("mode_type", 0)) not in ARTICLE_MODE_TYPES:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": "task not found"},
            )
        if task.get("status") == "failed":
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": task.get("error_message") or "task failed",
                    "status": "failed",
                    "task_id": task_id,
                    "error": task.get("error_message"),
                },
            )
        if task.get("status") not in FINAL_STATUSES or not task.get("article"):
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "message": "task not completed",
                    "status": task.get("status", "running"),
                    "task_id": task_id,
                },
            )
        return TaskDetailResponse(data=task)

    @router.get(
        "/tasks/{task_id}/export.docx",
        tags=["tasks"],
        response_model=None,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        summary="Export a completed task as a DOCX file",
    )
    async def export_task_docx(
        task_id: int,
        authorization: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> Response:
        auth_payload = resolve_auth_payload(services, authorization)
        if not auth_payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "valid bearer token is required"},
            )

        try:
            task = services.task_service.get_task(task_id)
        except Exception:
            logger.exception("Task service unavailable while exporting task_id=%s.", task_id)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"success": False, "message": "task service is temporarily unavailable"},
            )

        if not task:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": "task not found"},
            )
        if int(task.get("mode_type", 0)) not in ARTICLE_MODE_TYPES:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": "task not found"},
            )

        if task.get("status") != "completed" or not task.get("article"):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "task is not ready for export"},
            )

        binary, filename = services.doc_export_service.build_docx(task)
        quoted_filename = quote(filename)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}",
        }
        return Response(
            content=binary,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
        )

    return router
