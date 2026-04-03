from __future__ import annotations

from typing import Any

import requests

from .config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key) and not self.settings.llm_mock_mode

    def complete(self, prompt: str, *, expect_json: bool = False) -> str:
        if not self.enabled:
            raise RuntimeError("LLM client is not configured.")

        payload: dict[str, Any] = {
            "model": self.settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a senior content strategist and writer. "
                        "Follow the requested format exactly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        if expect_json:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            f"{self.settings.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.settings.openai_request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

