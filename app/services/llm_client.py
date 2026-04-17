from __future__ import annotations

from typing import Any

import requests

from app.core.config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enabled(self, provider: str = "openai") -> bool:
        if self.settings.llm_mock_mode:
            return False
        if provider == "anthropic":
            return self._openrouter_enabled()
        return self._azure_enabled() or self._openai_enabled()

    def complete(self, prompt: str, *, expect_json: bool = False, access_tier: str = "standard", provider: str = "openai") -> str:
        if not self.enabled(provider):
            raise RuntimeError("LLM client is disabled. Configure the corresponding API key or use mock mode.")

        if provider == "anthropic":
            return self._complete_with_openrouter(prompt, expect_json=expect_json, access_tier=access_tier)

        if self._azure_enabled():
            return self._complete_with_azure_responses(prompt, expect_json=expect_json, access_tier=access_tier)
        return self._complete_with_chat_completions(prompt, expect_json=expect_json)

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

    def _openrouter_model_for_tier(self, access_tier: str) -> str:
        if (access_tier or "").strip().lower() == "vip":
            return self.settings.openrouter_vip_model or self.settings.openrouter_standard_model
        return self.settings.openrouter_standard_model

    def _complete_with_azure_responses(self, prompt: str, *, expect_json: bool, access_tier: str) -> str:
        response = requests.post(
            self.settings.azure_openai_responses_url,
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
