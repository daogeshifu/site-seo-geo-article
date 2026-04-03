from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 5000
    debug: bool = True
    data_dir: Path = Path("data")
    cache_dir: Path = Path("data/cache")
    tasks_dir: Path = Path("data/tasks")
    max_workers: int = 2
    llm_mock_mode: bool = True
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    openai_request_timeout: int = 90

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("APP_DATA_DIR", "data"))
        return cls(
            host=os.getenv("FLASK_HOST", "127.0.0.1"),
            port=int(os.getenv("FLASK_PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "true").lower() == "true",
            data_dir=data_dir,
            cache_dir=data_dir / "cache",
            tasks_dir=data_dir / "tasks",
            max_workers=int(os.getenv("MAX_WORKERS", "2")),
            llm_mock_mode=os.getenv("LLM_MOCK_MODE", "true").lower() == "true",
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            openai_request_timeout=int(os.getenv("OPENAI_REQUEST_TIMEOUT", "90")),
        )

