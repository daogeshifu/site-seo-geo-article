from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


SupportedLanguage = Literal["English", "Chinese", "French", "German", "Dutch"]
SupportedCountry = Literal["us", "cn", "fr", "de", "nl"]


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


class InternalLinkRequest(BaseModel):
    label: str = Field(..., min_length=1, examples=["DELTA 3 Max Plus"])
    url: str = Field(..., min_length=1, examples=["https://de.ecoflow.com/products/delta-3-max-plus"])


class TaskContextRequest(BaseModel):
    country: SupportedCountry = "us"
    market: str = ""
    locale_variant: str = ""
    article_type: str = ""
    product_line: str = ""
    topic_flags: list[str] = Field(default_factory=list)
    mentions_other_brands: bool = False
    requires_shopify_link: bool = False
    shopify_url: str = ""
    ai_qa_content: str = ""
    ai_qa_source: str = ""
    internal_links: list[InternalLinkRequest] = Field(default_factory=list)


class TaskCreateRequest(BaseModel):
    category: str = Field(..., examples=["seo"])
    keyword: str = Field(..., examples=["portable charger on plane"])
    mode_type: int = Field(default=1, ge=1, le=2, examples=[1])
    info: str = ""
    brand_info: str = ""
    language: SupportedLanguage = "English"
    provider: str = Field(default="openai", examples=["openai", "anthropic"])
    word_limit: int = Field(default=1200, ge=200, le=10000)
    force_refresh: bool = False
    include_cover: int = Field(default=1, ge=0, le=1)
    content_image_count: int = Field(default=3, ge=0, le=3)
    task_context: TaskContextRequest = Field(default_factory=TaskContextRequest)

    model_config = {
        "json_schema_extra": {
            "example": {
                "category": "seo",
                "keyword": "portable charger on plane",
                "mode_type": 1,
                "info": "Brand: VoltGo. Product: 20000mAh portable charger.",
                "language": "English",
                "provider": "openai",
                "word_limit": 1200,
                "force_refresh": False,
                "include_cover": 1,
                "content_image_count": 2,
                "task_context": {
                    "country": "de",
                    "requires_shopify_link": True,
                    "shopify_url": "https://de.ecoflow.com/products/stream-microinverter",
                    "ai_qa_content": "AI answer summary for this keyword, if available.",
                    "ai_qa_source": "https://example.com/source-used-by-ai",
                },
            }
        }
    }


class TaskAcceptedData(BaseModel):
    task_id: int
    status: str
    access_tier: str
    mode_type: int


class TaskCreateResponse(BaseModel):
    success: bool = True
    data: TaskAcceptedData


class TaskListData(BaseModel):
    tasks: list[dict[str, Any]]


class TaskListResponse(BaseModel):
    success: bool = True
    data: TaskListData


class TaskDetailResponse(BaseModel):
    success: bool = True
    data: dict[str, Any]


class OutlineCreateRequest(BaseModel):
    category: str = Field(..., examples=["geo"])
    keyword: str = Field(..., examples=["Welke thuisbatterij heeft de beste app"])
    info: str = ""
    language: SupportedLanguage = "English"
    provider: str = Field(default="openai", examples=["openai", "anthropic"])
    word_limit: int = Field(default=1200, ge=200, le=10000)
    force_refresh: bool = False
    task_context: TaskContextRequest = Field(default_factory=TaskContextRequest)

    model_config = {
        "json_schema_extra": {
            "example": {
                "category": "geo",
                "keyword": "Welke thuisbatterij heeft de beste app",
                "info": "Brand: Anker SOLIX. Focus on home battery app experience and installation context.",
                "language": "Dutch",
                "provider": "openai",
                "word_limit": 1200,
                "force_refresh": False,
                "task_context": {
                    "country": "nl",
                    "requires_shopify_link": True,
                    "shopify_url": "https://www.ankersolix.com/nl/products/a17c5",
                    "ai_qa_content": "AI answer summary for this keyword, if available.",
                    "ai_qa_source": "https://example.com/source-used-by-ai",
                },
            }
        }
    }


class OutlineAcceptedData(BaseModel):
    outline_id: int
    status: str
    access_tier: str
    mode_type: int


class OutlineCreateResponse(BaseModel):
    success: bool = True
    data: OutlineAcceptedData


class OutlineData(BaseModel):
    category: str
    keyword: str
    info: str
    language: str
    task_context: dict[str, Any]
    title: str
    outline_markdown: str
    writing_suggestions: list[str]
    recommended_internal_links: list[dict[str, str]]
    generation_mode: str


class OutlineDetailResponse(BaseModel):
    success: bool = True
    data: dict[str, Any]


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
