from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from app.services.prompt_store import configure_prompt_store


@pytest.fixture(autouse=True)
def isolated_prompt_store(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Start every test from the default prompts, never a previous test's edits."""
    configure_prompt_store(tmp_path_factory.mktemp("prompts") / "prompts.json")
