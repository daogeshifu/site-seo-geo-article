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
            "Async article and outline generation service with SEO/GEO writing modes, 1-day bearer auth, "
            "keyword-level cache, and optional Azure image generation.\n\n"
            "## Step 1: Exchange Token\n"
            "Use an access key to get a 1-day bearer token before calling the task APIs.\n\n"
            "**Token helper endpoint**: `POST /api/token`\n\n"
            "```bash\n"
            "curl -X POST http://127.0.0.1:8028/api/token \\\n"
            "  -H \"Content-Type: application/json\" \\\n"
            "  -d '{\"access_key\":\"YOUR_ACCESS_KEY\"}'\n"
            "```\n\n"
            "Example response:\n\n"
            "```json\n"
            "{\n"
            "  \"success\": true,\n"
            "  \"data\": {\n"
            "    \"access_token\": \"YOUR_BEARER_TOKEN\",\n"
            "    \"token_type\": \"bearer\",\n"
            "    \"access_tier\": \"vip\",\n"
            "    \"expires_in\": 86400,\n"
            "    \"expires_at\": \"2026-04-10T12:00:00Z\"\n"
            "  }\n"
            "}\n"
            "```\n\n"
            "## Step 2A: Create Outline Task\n"
            "Call `POST /api/outline` with `Authorization: Bearer YOUR_BEARER_TOKEN`.\n\n"
            "## Step 3A: Get Outline Result\n"
            "Call `GET /api/outline/{outline_id}` with the same bearer token.\n\n"
            "## Step 2B: Create Article Task\n"
            "Call `POST /api/tasks` with `Authorization: Bearer YOUR_BEARER_TOKEN`.\n\n"
            "## Step 3B: Get Article Task Result\n"
            "Call `GET /api/tasks/{task_id}` with the same bearer token."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {
                "name": "auth",
                "description": "Exchange an access key for a short-lived bearer token.",
            },
            {
                "name": "tasks",
                "description": "Create outline or article generation tasks and fetch task results.",
            },
        ],
    )
    app.state.services = services
    app.mount("/static", StaticFiles(directory=str(app_root / "web" / "static")), name="static")
    app.include_router(create_web_router(services))
    app.include_router(create_api_router(services))
    return app
