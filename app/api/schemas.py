from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TokenExchangeRequest(BaseModel):
    access_key: str = Field(..., min_length=1, examples=["demo-vip-access-key"])


class TokenExchangeData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    access_tier: str
    expires_in: int
    expires_at: str


class TokenExchangeResponse(BaseModel):
    success: bool = True
    data: TokenExchangeData


class TaskCreateRequest(BaseModel):
    category: str = Field(..., examples=["seo"])
    keyword: str = Field(..., examples=["portable charger on plane"])
    info: str = ""
    brand_info: str = ""
    language: str = "English"
    word_limit: int = Field(default=1200, ge=200, le=10000)
    force_refresh: bool = False
    include_cover: int = Field(default=1, ge=0, le=1)
    content_image_count: int = Field(default=3, ge=0, le=3)

    model_config = {
        "json_schema_extra": {
            "example": {
                "category": "seo",
                "keyword": "portable charger on plane",
                "info": "Brand: VoltGo. Product: 20000mAh portable charger.",
                "language": "English",
                "word_limit": 1200,
                "force_refresh": False,
                "include_cover": 1,
                "content_image_count": 2,
            }
        }
    }


class TaskAcceptedData(BaseModel):
    task_id: int
    status: str
    access_tier: str


class TaskCreateResponse(BaseModel):
    success: bool = True
    data: TaskAcceptedData


class TaskDetailResponse(BaseModel):
    success: bool = True
    data: dict[str, Any]


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
