from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def issue_token(self, access_key: str) -> dict[str, Any] | None:
        tier = self.resolve_access_tier(access_key)
        if not tier:
            return None

        issued_at = int(time.time())
        expires_at = issued_at + self.settings.token_ttl_seconds
        payload = {
            "tier": tier,
            "iat": issued_at,
            "exp": expires_at,
        }
        encoded = self._encode_payload(payload)
        signature = self._sign(encoded)
        return {
            "access_token": f"{encoded}.{signature}",
            "token_type": "bearer",
            "access_tier": tier,
            "expires_in": self.settings.token_ttl_seconds,
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }

    def verify_token(self, token: str) -> dict[str, Any] | None:
        token = token.strip()
        if not token or "." not in token:
            return None

        encoded, signature = token.rsplit(".", 1)
        expected = self._sign(encoded)
        if not hmac.compare_digest(signature, expected):
            return None

        try:
            payload = json.loads(self._decode_payload(encoded))
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            return None

        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if payload.get("tier") not in {"standard", "vip"}:
            return None
        return payload

    def resolve_access_tier(self, access_key: str) -> str | None:
        access_key = access_key.strip()
        if not access_key:
            return None
        if self.settings.vip_access_key and access_key == self.settings.vip_access_key:
            return "vip"
        if self.settings.normal_access_key and access_key == self.settings.normal_access_key:
            return "standard"
        return None

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    def _decode_payload(self, payload: str) -> str:
        padding = "=" * (-len(payload) % 4)
        return base64.urlsafe_b64decode(f"{payload}{padding}").decode("utf-8")

    def _sign(self, encoded_payload: str) -> str:
        return hmac.new(
            self.settings.token_signing_secret.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
