from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from app.core.config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enabled(self, provider: str = "openai") -> bool:
        provider_kind = self.provider_kind(provider)
        if self.settings.llm_mock_mode:
            return False
        if provider_kind == "anthropic":
            return self._openrouter_enabled()
        if provider_kind == "azure":
            return self._azure_enabled()
        if provider_kind == "openai":
            return self._openai_enabled() or self._azure_enabled()
        return self._azure_enabled() or self._openai_enabled()

    def complete(self, prompt: str, *, expect_json: bool = False, access_tier: str = "standard", provider: str = "openai") -> str:
        if not self.enabled(provider):
            raise RuntimeError("LLM client is disabled. Configure the corresponding API key or use mock mode.")

        provider_kind = self.provider_kind(provider)

        if provider_kind == "anthropic":
            return self._complete_with_openrouter(prompt, expect_json=expect_json, access_tier=access_tier)

        if provider_kind == "azure":
            return self._complete_with_azure_responses(prompt, expect_json=expect_json, access_tier=access_tier)
        if provider_kind == "openai" and self._openai_enabled() and not self._azure_enabled():
            return self._complete_with_chat_completions(prompt, expect_json=expect_json)
        if self._azure_enabled():
            return self._complete_with_azure_responses(prompt, expect_json=expect_json, access_tier=access_tier)
        return self._complete_with_chat_completions(prompt, expect_json=expect_json)

    def resolve_execution_provider(self, provider: str = "openai", access_tier: str = "standard") -> str:
        provider_kind = self.provider_kind(provider)
        if provider_kind == "anthropic":
            return f"openrouter:{self._openrouter_model_for_tier(access_tier)}"
        if provider_kind == "azure":
            return f"azure:{self._model_for_tier(access_tier)}"
        if provider_kind == "openai":
            if self._azure_enabled():
                return f"azure:{self._model_for_tier(access_tier)}"
            return f"openai:{self.settings.openai_model}"
        return provider.strip().lower() or "openai"

    @staticmethod
    def provider_kind(provider: str = "openai") -> str:
        normalized = (provider or "openai").strip().lower()
        if normalized in {"anthropic", "openrouter"} or normalized.startswith("openrouter:"):
            return "anthropic"
        if normalized.startswith("azure:"):
            return "azure"
        if normalized.startswith("openai:"):
            return "openai"
        if normalized in {"openai", "azure"}:
            return normalized
        return "openai"

    def _azure_enabled(self) -> bool:
        return bool(self.settings.azure_openai_api_key and self.settings.azure_openai_responses_url)

    def _openai_enabled(self) -> bool:
        return bool(self.settings.openai_api_key)

    def _openrouter_enabled(self) -> bool:
        return bool(self.settings.openrouter_api_key)

    def _model_for_tier(self, access_tier: str) -> str:
        if (access_tier or "").strip().lower() == "vip":
            return self.settings.azure_openai_vip_model or self.settings.azure_openai_standard_model
        return self.settings.azure_openai_standard_model

    def _azure_api_version_for_tier(self, access_tier: str) -> str:
        if (access_tier or "").strip().lower() == "vip":
            return self.settings.azure_openai_vip_api_version or self.settings.azure_openai_standard_api_version
        return self.settings.azure_openai_standard_api_version or self.settings.azure_openai_vip_api_version

    def _azure_responses_url_for_tier(self, access_tier: str) -> str:
        raw_url = self.settings.azure_openai_responses_url.strip()
        if not raw_url:
            return raw_url
        api_version = self._azure_api_version_for_tier(access_tier)
        if not api_version:
            return raw_url

        parts = urlsplit(raw_url)
        query_items = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "api-version"]
        query_items.append(("api-version", api_version))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))

    def _openrouter_model_for_tier(self, access_tier: str) -> str:
        if (access_tier or "").strip().lower() == "vip":
            return self.settings.openrouter_vip_model or self.settings.openrouter_standard_model
        return self.settings.openrouter_standard_model

    def _complete_with_azure_responses(self, prompt: str, *, expect_json: bool, access_tier: str) -> str:
        response = requests.post(
            self._azure_responses_url_for_tier(access_tier),
            headers={
                "Content-Type": "application/json",
                "api-key": self.settings.azure_openai_api_key,
            },
            json={
                "model": self._model_for_tier(access_tier),
                "input": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "You are a precise writing assistant. "
                                    "Follow formatting rules exactly."
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt}],
                    },
                ],
            },
            timeout=self.settings.openai_request_timeout,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))

        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        fragments: list[str] = []
        for item in payload.get("output") or []:
            if item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    fragments.append(content["text"])
        text = "\n".join(fragment for fragment in fragments if fragment.strip()).strip()
        if not text:
            raise RuntimeError("No response text returned from Azure Responses API.")
        return text

    def _complete_with_chat_completions(self, prompt: str, *, expect_json: bool) -> str:
        response = requests.post(
            f"{self.settings.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.openai_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise writing assistant. Follow formatting rules exactly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"} if expect_json else None,
            },
            timeout=self.settings.openai_request_timeout,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("No completion choices returned.")
        return choices[0]["message"]["content"]

    def _complete_with_openrouter(self, prompt: str, *, expect_json: bool, access_tier: str) -> str:
        response = requests.post(
            f"{self.settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._openrouter_model_for_tier(access_tier),
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise writing assistant. Follow formatting rules exactly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"} if expect_json else None,
            },
            timeout=self.settings.openrouter_request_timeout,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("No completion choices returned from OpenRouter.")
        return choices[0]["message"]["content"]
