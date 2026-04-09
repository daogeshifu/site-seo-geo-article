from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import create_api_router
from app.core.runtime import build_services
from app.web.routes import create_web_router


def create_app(config_override: dict[str, Any] | None = None) -> FastAPI:
    app_root = Path(__file__).resolve().parent.parent
    services = build_services(config_override)

    app = FastAPI(
        title="SEO / GEO Article Writer API",
        description=(
            "Async article generation service with SEO/GEO writing modes, 1-day bearer auth, "
            "keyword-level cache, and optional Azure image generation."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.services = services
    app.mount("/static", StaticFiles(directory=str(app_root / "web" / "static")), name="static")
    app.include_router(create_web_router(services))
    app.include_router(create_api_router(services))
    return app
