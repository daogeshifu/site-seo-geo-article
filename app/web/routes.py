from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.runtime import AppServices
from app.web.context import build_demo_page_context


def create_web_router(services: AppServices) -> APIRouter:
    router = APIRouter(tags=["web"])

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request) -> HTMLResponse:
        context = build_demo_page_context(
            llm_enabled=services.writer_service.llm_client.enabled(),
            image_enabled=services.image_service.enabled,
            image_mode=services.image_service.mode,
            page_title="SEO / GEO Article Writer Console",
            active_demo="article",
        )
        context["request"] = request
        context["static_version"] = "20260423-mode-type-v2"
        return services.templates.TemplateResponse(request, "demo/index.html", context)

    @router.get("/outline", response_class=HTMLResponse, include_in_schema=False)
    async def outline(request: Request) -> HTMLResponse:
        context = build_demo_page_context(
            llm_enabled=services.outline_service.llm_client.enabled(),
            image_enabled=services.image_service.enabled,
            image_mode=services.image_service.mode,
            page_title="SEO / GEO Outline Writer Console",
            active_demo="outline",
        )
        context["request"] = request
        context["static_version"] = "20260423-mode-type-v2"
        return services.templates.TemplateResponse(request, "demo/outline.html", context)

    @router.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> RedirectResponse:
        return RedirectResponse(url="/static/demo/favicon.svg", status_code=307)

    return router
