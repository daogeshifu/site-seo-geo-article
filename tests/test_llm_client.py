from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.services.llm_client import LLMClient


class _DummyResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_llm_client_uses_azure_responses_and_standard_model(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        llm_mock_mode=False,
        azure_openai_api_key="azure-key",
        azure_openai_responses_url="https://suzhou-gpt5.cognitiveservices.azure.com/openai/responses",
        azure_openai_standard_model="gpt-5.4-mini",
        azure_openai_vip_model="gpt-5.4-pro",
        azure_openai_standard_api_version="2025-04-01-preview",
        azure_openai_vip_api_version="2025-05-01-preview",
    )
    client = LLMClient(settings)
    captured: dict[str, Any] = {}

    def fake_post(url: str, *, headers: dict[str, Any], json: dict[str, Any], timeout: int) -> _DummyResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _DummyResponse({"output_text": "draft article"})

    monkeypatch.setattr("app.services.llm_client.requests.post", fake_post)

    text = client.complete("write me an article", access_tier="standard")

    assert text == "draft article"
    assert captured["url"] == "https://suzhou-gpt5.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview"
    assert captured["headers"]["api-key"] == "azure-key"
    assert captured["json"]["model"] == "gpt-5.4-mini"
    assert captured["json"]["input"][1]["content"][0]["text"] == "write me an article"


def test_llm_client_uses_vip_model_for_vip_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        llm_mock_mode=False,
        azure_openai_api_key="azure-key",
        azure_openai_responses_url="https://suzhou-gpt5.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview",
        azure_openai_standard_model="gpt-5.4-mini",
        azure_openai_vip_model="gpt-5.4-pro",
        azure_openai_standard_api_version="2025-04-01-preview",
        azure_openai_vip_api_version="2025-05-01-preview",
    )
    client = LLMClient(settings)
    captured: dict[str, Any] = {}

    def fake_post(url: str, *, headers: dict[str, Any], json: dict[str, Any], timeout: int) -> _DummyResponse:
        captured["url"] = url
        captured["json"] = json
        return _DummyResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "{\"ok\": true}"}],
                    }
                ]
            }
        )

    monkeypatch.setattr("app.services.llm_client.requests.post", fake_post)

    text = client.complete("return json", expect_json=True, access_tier="vip")

    assert text == "{\"ok\": true}"
    assert captured["url"] == "https://suzhou-gpt5.cognitiveservices.azure.com/openai/responses?api-version=2025-05-01-preview"
    assert captured["json"]["model"] == "gpt-5.4-pro"


def test_llm_client_resolves_execution_provider_by_backend_and_tier() -> None:
    settings = Settings(
        llm_mock_mode=False,
        azure_openai_api_key="azure-key",
        azure_openai_responses_url="https://suzhou-gpt5.cognitiveservices.azure.com/openai/responses",
        azure_openai_standard_model="gpt-5.4-mini",
        azure_openai_vip_model="gpt-5.4-pro",
        openrouter_api_key="router-key",
        openrouter_standard_model="anthropic/claude-haiku-4.5",
        openrouter_vip_model="anthropic/claude-opus-4-6",
    )
    client = LLMClient(settings)

    assert client.resolve_execution_provider("openai", "standard") == "azure:gpt-5.4-mini"
    assert client.resolve_execution_provider("openai", "vip") == "azure:gpt-5.4-pro"
    assert client.resolve_execution_provider("anthropic", "vip") == "openrouter:anthropic/claude-opus-4-6"
