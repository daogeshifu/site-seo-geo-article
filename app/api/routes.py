from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.runtime import AppServices
from app.services.task_service import FINAL_STATUSES
from .schemas import (
    ErrorResponse,
    TaskAcceptedData,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskDetailResponse,
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
        info = (payload.info or payload.brand_info or "").strip()
        language = (payload.language or "English").strip() or "English"
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

        try:
            task = services.task_service.create_task(
                category=category,
                keyword=keyword,
                info=info,
                language=language,
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
            )
        )

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

    return router
