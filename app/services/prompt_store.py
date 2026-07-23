"""Runtime storage for editable prompt templates.

Defaults live in ``prompt_templates``. Overrides are persisted as JSON so the
admin console can change any prompt while the service keeps running. The file is
re-read whenever its modification time changes, which keeps every worker process
in sync without a restart.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.prompt_templates import TEMPLATES, TEMPLATES_BY_KEY, PromptTemplate

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def render_template(text: str, values: dict[str, Any]) -> str:
    """Replace ``{{name}}`` placeholders. Unknown names render as empty text."""

    def _replace(match: re.Match[str]) -> str:
        return str(values.get(match.group(1), ""))

    return PLACEHOLDER_PATTERN.sub(_replace, text)


def placeholders_in(text: str) -> list[str]:
    seen: list[str] = []
    for name in PLACEHOLDER_PATTERN.findall(text):
        if name not in seen:
            seen.append(name)
    return seen


class PromptStore:
    def __init__(self, file_path: Path, backup_dir: Path | None = None) -> None:
        self.file_path = Path(file_path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.file_path.parent / "prompt_backups"
        self._lock = threading.RLock()
        self._overrides: dict[str, str] = {}
        self._loaded_mtime: float | None = None
        self._updated_at: dict[str, str] = {}
        self._load(force=True)

    # ---- reading -----------------------------------------------------
    def text(self, key: str) -> str:
        template = TEMPLATES_BY_KEY.get(key)
        if template is None:
            raise KeyError(f"unknown prompt key: {key}")
        self._load()
        with self._lock:
            return self._overrides.get(key, template.default)

    def render(self, key: str, **values: Any) -> str:
        return render_template(self.text(key), values).strip()

    def items(self) -> list[dict[str, Any]]:
        self._load()
        with self._lock:
            return [self._describe(template) for template in TEMPLATES]

    def item(self, key: str) -> dict[str, Any]:
        template = TEMPLATES_BY_KEY.get(key)
        if template is None:
            raise KeyError(f"unknown prompt key: {key}")
        self._load()
        with self._lock:
            return self._describe(template)

    def _describe(self, template: PromptTemplate) -> dict[str, Any]:
        text = self._overrides.get(template.key, template.default)
        return {
            "key": template.key,
            "group": template.group,
            "name": template.name,
            "description": template.description,
            "variables": list(template.variables),
            "text": text,
            "default": template.default,
            "customized": template.key in self._overrides,
            "updated_at": self._updated_at.get(template.key, ""),
            "unknown_variables": [
                name for name in placeholders_in(text) if name not in template.variables
            ],
            "missing_variables": [
                name for name in template.variables if name not in placeholders_in(text)
            ],
        }

    # ---- writing -----------------------------------------------------
    def update(self, key: str, text: str) -> dict[str, Any]:
        template = TEMPLATES_BY_KEY.get(key)
        if template is None:
            raise KeyError(f"unknown prompt key: {key}")
        normalized = text.replace("\r\n", "\n").strip()
        if not normalized:
            raise ValueError("prompt text cannot be empty")
        self._load()
        with self._lock:
            if normalized == template.default:
                self._overrides.pop(key, None)
                self._updated_at.pop(key, None)
            else:
                self._overrides[key] = normalized
                self._updated_at[key] = _now()
            self._save()
            return self._describe(template)

    def reset(self, key: str) -> dict[str, Any]:
        template = TEMPLATES_BY_KEY.get(key)
        if template is None:
            raise KeyError(f"unknown prompt key: {key}")
        self._load()
        with self._lock:
            self._overrides.pop(key, None)
            self._updated_at.pop(key, None)
            self._save()
            return self._describe(template)

    def reset_all(self) -> None:
        with self._lock:
            self._overrides.clear()
            self._updated_at.clear()
            self._save()

    # ---- global backups ----------------------------------------------
    def create_backup(self, note: str = "") -> dict[str, Any]:
        """Snapshot the current state of every prompt into a new backup file."""
        self._load()
        with self._lock:
            payload = {
                "id": self._next_backup_id(),
                "created_at": _now(),
                "note": note.strip()[:120],
                "prompts": dict(self._overrides),
            }
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            path = self.backup_dir / f"{payload['id']}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return _describe_backup(payload)

    def list_backups(self) -> list[dict[str, Any]]:
        backups = []
        for path in self.backup_dir.glob("*.json"):
            payload = self._read_backup(path)
            if payload:
                backups.append(_describe_backup(payload))
        backups.sort(key=lambda item: _backup_sort_key(item["id"]), reverse=True)
        return backups

    def delete_backup(self, backup_id: str) -> None:
        path = self._backup_path(backup_id)
        if not path.exists():
            raise KeyError(f"unknown backup: {backup_id}")
        path.unlink()

    def restore_backup(self, backup_id: str) -> dict[str, Any]:
        """Replace the current prompts with a backup, snapshotting the state first."""
        payload = self._read_backup(self._backup_path(backup_id))
        if payload is None:
            raise KeyError(f"unknown backup: {backup_id}")
        self.create_backup(note=f"恢复 {backup_id} 前的自动备份")
        restored_at = _now()
        with self._lock:
            self._overrides = {
                key: text
                for key, text in (payload.get("prompts") or {}).items()
                if key in TEMPLATES_BY_KEY and isinstance(text, str)
            }
            self._updated_at = {key: restored_at for key in self._overrides}
            self._save()
        return _describe_backup(payload)

    def _backup_path(self, backup_id: str) -> Path:
        if not re.fullmatch(r"[0-9]{8}-[0-9]{6}(-[0-9]+)?", backup_id or ""):
            raise KeyError(f"unknown backup: {backup_id}")
        return self.backup_dir / f"{backup_id}.json"

    def _next_backup_id(self) -> str:
        base = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        candidate, suffix = base, 1
        while (self.backup_dir / f"{candidate}.json").exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _read_backup(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) and payload.get("id") else None

    # ---- persistence -------------------------------------------------
    def _load(self, force: bool = False) -> None:
        with self._lock:
            try:
                mtime = self.file_path.stat().st_mtime
            except OSError:
                if force or self._loaded_mtime is not None:
                    self._overrides = {}
                    self._updated_at = {}
                    self._loaded_mtime = None
                return
            if not force and mtime == self._loaded_mtime:
                return
            try:
                payload = json.loads(self.file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            prompts = payload.get("prompts") if isinstance(payload, dict) else None
            overrides: dict[str, str] = {}
            updated_at: dict[str, str] = {}
            for key, value in (prompts or {}).items():
                if key not in TEMPLATES_BY_KEY:
                    continue
                if isinstance(value, str):
                    overrides[key] = value
                elif isinstance(value, dict) and isinstance(value.get("text"), str):
                    overrides[key] = value["text"]
                    updated_at[key] = str(value.get("updated_at") or "")
            self._overrides = overrides
            self._updated_at = updated_at
            self._loaded_mtime = mtime

    def _save(self) -> None:
        payload = {
            "version": 1,
            "saved_at": _now(),
            "prompts": {
                key: {"text": text, "updated_at": self._updated_at.get(key, "")}
                for key, text in self._overrides.items()
            },
        }
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)
        try:
            self._loaded_mtime = self.file_path.stat().st_mtime
        except OSError:
            self._loaded_mtime = None


def _backup_sort_key(backup_id: str) -> tuple[str, int]:
    """Sort ``20260723-052725-1`` after ``20260723-052725``: same second, written later."""
    timestamp, _, counter = backup_id.rpartition("-")
    if counter.isdigit() and len(counter) < 6:
        return timestamp, int(counter)
    return backup_id, 0


def _describe_backup(payload: dict[str, Any]) -> dict[str, Any]:
    prompts = payload.get("prompts") or {}
    return {
        "id": str(payload.get("id") or ""),
        "created_at": str(payload.get("created_at") or ""),
        "note": str(payload.get("note") or ""),
        "customized_count": len(prompts),
        "total_count": len(TEMPLATES_BY_KEY),
    }


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


_store: PromptStore | None = None
_store_lock = threading.Lock()


def configure_prompt_store(file_path: Path) -> PromptStore:
    """Point the shared store at a specific file (called during app startup)."""
    global _store
    with _store_lock:
        _store = PromptStore(file_path)
        return _store


def get_prompt_store() -> PromptStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = PromptStore(Path(os.getenv("APP_DATA_DIR", "data")) / "prompts.json")
        return _store
