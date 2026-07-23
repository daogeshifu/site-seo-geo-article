"""Prompt admin console: login, prompt CRUD and live prompt preview."""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.runtime import AppServices
from app.services.prompt_builder import build_draft_prompt, build_polish_prompt, build_strategy_prompt

SESSION_COOKIE = "prompt_admin_session"
STATIC_VERSION = "20260723-prompt-admin-backups"

SAMPLE_HTML = (
    "<h1>Sample article title</h1>"
    "<p><strong>Quick Answer:</strong> A short extractable answer paragraph.</p>"
    "<h2>Sample body section</h2><p>Body copy used only for preview.</p>"
)


def _sign(secret: str, value: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _issue_session(services: AppServices) -> str:
    expires_at = int(time.time()) + services.settings.admin_session_ttl_seconds
    payload = f"admin:{expires_at}"
    return f"{payload}.{_sign(services.settings.token_signing_secret, payload)}"


def _is_authenticated(services: AppServices, request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE, "")
    if "." not in token:
        return False
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(services.settings.token_signing_secret, payload)):
        return False
    scope, _, expires_at = payload.partition(":")
    if scope != "admin" or not expires_at.isdigit():
        return False
    return int(expires_at) > int(time.time())


def create_admin_router(services: AppServices) -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin"], include_in_schema=False)
    store = services.prompt_store

    def render_login(request: Request, error: str = "") -> HTMLResponse:
        return services.templates.TemplateResponse(
            request,
            "admin/login.html",
            {
                "request": request,
                "page_title": "提示词后台 · 登录",
                "static_version": STATIC_VERSION,
                "error": error,
                "password_configured": bool(services.settings.admin_password),
            },
            status_code=401 if error else 200,
        )

    def guard(request: Request) -> JSONResponse | None:
        if not services.settings.admin_password:
            return JSONResponse(
                status_code=503,
                content={"success": False, "message": "未配置 ADMIN_PASSWORD，后台不可用"},
            )
        if not _is_authenticated(services, request):
            return JSONResponse(status_code=401, content={"success": False, "message": "登录已失效，请重新登录"})
        return None

    @router.get("", response_class=HTMLResponse)
    async def console(request: Request) -> HTMLResponse:
        if not services.settings.admin_password or not _is_authenticated(services, request):
            return render_login(request)
        return services.templates.TemplateResponse(
            request,
            "admin/prompts.html",
            {
                "request": request,
                "page_title": "提示词后台",
                "static_version": STATIC_VERSION,
                "storage_path": str(store.file_path),
            },
        )

    @router.post("/login", response_model=None)
    async def login(request: Request, password: str = Form("")) -> HTMLResponse | RedirectResponse:
        configured = services.settings.admin_password
        if not configured:
            return render_login(request, "服务端未配置 ADMIN_PASSWORD")
        if not hmac.compare_digest(password.strip(), configured):
            return render_login(request, "密码不正确")
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            _issue_session(services),
            max_age=services.settings.admin_session_ttl_seconds,
            httponly=True,
            samesite="lax",
        )
        return response

    @router.post("/logout")
    async def logout() -> RedirectResponse:
        response = RedirectResponse(url="/admin", status_code=303)
        response.delete_cookie(SESSION_COOKIE)
        return response

    @router.get("/api/prompts")
    async def list_prompts(request: Request) -> JSONResponse:
        denied = guard(request)
        if denied:
            return denied
        return JSONResponse({"success": True, "data": {"items": store.items()}})

    @router.put("/api/prompts/{key}")
    async def update_prompt(request: Request, key: str) -> JSONResponse:
        denied = guard(request)
        if denied:
            return denied
        body = await request.json()
        try:
            item = store.update(key, str(body.get("text") or ""))
        except KeyError:
            return JSONResponse(status_code=404, content={"success": False, "message": "提示词不存在"})
        except ValueError as error:
            return JSONResponse(status_code=400, content={"success": False, "message": str(error)})
        return JSONResponse({"success": True, "data": item})

    @router.post("/api/prompts/{key}/reset")
    async def reset_prompt(request: Request, key: str) -> JSONResponse:
        denied = guard(request)
        if denied:
            return denied
        try:
            item = store.reset(key)
        except KeyError:
            return JSONResponse(status_code=404, content={"success": False, "message": "提示词不存在"})
        return JSONResponse({"success": True, "data": item})

    @router.get("/api/backups")
    async def list_backups(request: Request) -> JSONResponse:
        denied = guard(request)
        if denied:
            return denied
        return JSONResponse({"success": True, "data": {"items": store.list_backups()}})

    @router.post("/api/backups")
    async def create_backup(request: Request) -> JSONResponse:
        denied = guard(request)
        if denied:
            return denied
        body = await request.json()
        item = store.create_backup(str(body.get("note") or ""))
        return JSONResponse({"success": True, "data": item})

    @router.post("/api/backups/{backup_id}/restore")
    async def restore_backup(request: Request, backup_id: str) -> JSONResponse:
        denied = guard(request)
        if denied:
            return denied
        try:
            item = store.restore_backup(backup_id)
        except KeyError:
            return JSONResponse(status_code=404, content={"success": False, "message": "备份不存在"})
        return JSONResponse({"success": True, "data": item})

    @router.delete("/api/backups/{backup_id}")
    async def delete_backup(request: Request, backup_id: str) -> JSONResponse:
        denied = guard(request)
        if denied:
            return denied
        try:
            store.delete_backup(backup_id)
        except KeyError:
            return JSONResponse(status_code=404, content={"success": False, "message": "备份不存在"})
        return JSONResponse({"success": True, "data": {"id": backup_id}})

    @router.post("/api/preview")
    async def preview(request: Request) -> JSONResponse:
        denied = guard(request)
        if denied:
            return denied
        body = await request.json()
        stage = str(body.get("stage") or "strategy")
        category = "geo" if str(body.get("category")).lower() == "geo" else "seo"
        keyword = str(body.get("keyword") or "").strip() or "portable home battery"
        info = str(body.get("info") or "").strip()
        language = str(body.get("language") or "English").strip() or "English"
        word_limit = max(200, int(body.get("word_limit") or 1200))
        mode_type = 2 if int(body.get("mode_type") or 1) == 2 else 1
        content_version = "3.0" if str(body.get("content_version")) == "3.0" else "2.0"

        rulebook = services.outline_service.rulebook_service
        task_context = rulebook.normalize_task_context(
            {"content_version": content_version, "publishing_context": body.get("publishing_context") or ""}
        )
        rule_context = rulebook.resolve_rules(category=category, language=language, task_context=task_context)

        if stage == "draft":
            text = build_draft_prompt(
                category, keyword, info, language, {"h1_options": [keyword]}, rule_context, word_limit, mode_type
            )
        elif stage == "polish":
            text = build_polish_prompt(category, language, keyword, SAMPLE_HTML, rule_context, word_limit, mode_type)
        elif stage == "outline":
            text = services.outline_service._build_prompt(
                category=category,
                keyword=keyword,
                info=info,
                language=language,
                rule_context=rule_context,
                available_links=[],
                word_limit=word_limit,
            )
        else:
            text = build_strategy_prompt(category, keyword, info, language, rule_context, word_limit, mode_type)

        return JSONResponse({"success": True, "data": {"stage": stage, "prompt": text}})

    return router
