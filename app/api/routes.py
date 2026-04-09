from __future__ import annotations

from fastapi import APIRouter, Header, status
from fastapi.responses import JSONResponse

from app.core.runtime import AppServices
from app.utils.common import split_keywords
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


def resolve_auth_payload(services: AppServices, authorization: str | None) -> dict[str, str] | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return services.auth_service.verify_token(token)


def create_api_router(services: AppServices) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["api"])

    @router.post(
        "/token",
        include_in_schema=False,
        response_model=TokenExchangeResponse,
        responses={403: {"model": ErrorResponse}},
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
        response_model=TaskCreateResponse,
        responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
        summary="Create an async article generation task",
    )
    async def create_task(
        payload: TaskCreateRequest,
        authorization: str | None = Header(default=None),
    ) -> TaskCreateResponse | JSONResponse:
        category = payload.category.strip().lower()
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

        keywords = split_keywords(payload.keywords)
        if not keywords:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "keywords is required"},
            )

        task = services.task_service.create_task(
            category=category,
            keywords=keywords,
            info=info,
            language=language,
            force_refresh=payload.force_refresh,
            include_cover=payload.include_cover,
            content_image_count=payload.content_image_count,
            access_tier=auth_payload["tier"],
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
        response_model=TaskDetailResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        summary="Fetch an async task result",
    )
    async def get_task(
        task_id: str,
        authorization: str | None = Header(default=None),
    ) -> TaskDetailResponse | JSONResponse:
        auth_payload = resolve_auth_payload(services, authorization)
        if not auth_payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "valid bearer token is required"},
            )

        task = services.task_service.get_task(task_id)
        if not task:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": "task not found"},
            )
        return TaskDetailResponse(data=task)

    return router
