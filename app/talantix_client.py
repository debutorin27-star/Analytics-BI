from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class TalantixError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        details: Any | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details
        self.request_id = request_id


class TokenStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path = Path(settings.talantix_token_file).expanduser() if settings.talantix_token_file else None
        self._tokens = self._load_tokens()

    @property
    def access_token(self) -> str | None:
        return self._tokens.get("access_token")

    @property
    def refresh_token(self) -> str | None:
        return self._tokens.get("refresh_token")

    def should_refresh(self, skew_seconds: int = 60) -> bool:
        expires_in = self._tokens.get("expires_in")
        created_at = self._tokens.get("created_at")
        if not expires_in or not created_at or not self.refresh_token:
            return False

        created_at_seconds = float(created_at) / 1000 if float(created_at) > 10_000_000_000 else float(created_at)
        return time.time() >= created_at_seconds + float(expires_in) - skew_seconds

    def update(self, token_payload: dict[str, Any]) -> None:
        payload = dict(token_payload)
        payload.setdefault("created_at", int(time.time() * 1000))
        self._tokens.update(payload)
        if not self._path:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self._tokens, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self._path)

    def _load_tokens(self) -> dict[str, Any]:
        if self._path and self._path.exists():
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
            except json.JSONDecodeError as exc:
                raise TalantixError(f"Invalid token file JSON: {self._path}", status_code=500) from exc

        payload: dict[str, Any] = {}
        if self._settings.talantix_access_token:
            payload["access_token"] = self._settings.talantix_access_token
        if self._settings.talantix_refresh_token:
            payload["refresh_token"] = self._settings.talantix_refresh_token
        return payload


class TalantixClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token_store = TokenStore(settings)
        self._client = httpx.AsyncClient(
            base_url=settings.talantix_base_url.rstrip("/"),
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0),
            headers={
                "Content-Type": "application/json",
                "User-Agent": settings.talantix_user_agent,
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def auth_check(self) -> dict[str, Any]:
        response = await self._request("GET", "/auth_check", json_body=None, refresh_on_401=True)
        return {"ok": response.status_code == 204, "status_code": response.status_code}

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        if self._token_store.should_refresh():
            await self._refresh_tokens()

        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name

        response = await self._request("POST", "/graphql", json_body=payload, refresh_on_401=True)
        try:
            body = response.json()
        except ValueError as exc:
            raise TalantixError(
                "Talantix returned a non-JSON response",
                details=response.text[:1000],
                request_id=response.headers.get("X-Request-Id"),
            ) from exc

        errors = body.get("errors")
        if errors:
            raise TalantixError(
                "Talantix GraphQL error",
                details=errors,
                request_id=response.headers.get("X-Request-Id"),
            )
        return body

    async def post_form(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        response = await self._client.post(
            path,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": self._settings.talantix_user_agent,
            },
        )
        if response.is_error:
            raise TalantixError(
                f"Talantix form request failed with HTTP {response.status_code}",
                status_code=502,
                details=_safe_json(response),
                request_id=response.headers.get("X-Request-Id"),
            )
        return response.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None,
        refresh_on_401: bool,
    ) -> httpx.Response:
        access_token = self._token_store.access_token
        if not access_token:
            raise TalantixError("TALANTIX_ACCESS_TOKEN is not configured", status_code=500)

        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self._client.request(method, path, json=json_body, headers=headers)
        if response.status_code == 401 and refresh_on_401 and self._token_store.refresh_token:
            await self._refresh_tokens()
            headers = {"Authorization": f"Bearer {self._token_store.access_token}"}
            response = await self._client.request(method, path, json=json_body, headers=headers)

        if response.is_error:
            raise TalantixError(
                f"Talantix request failed with HTTP {response.status_code}",
                status_code=502,
                details=_safe_json(response),
                request_id=response.headers.get("X-Request-Id"),
            )
        return response

    async def _refresh_tokens(self) -> None:
        refresh_token = self._token_store.refresh_token
        if not refresh_token:
            raise TalantixError("Talantix refresh token is not configured", status_code=500)

        logger.info("Refreshing Talantix access token")
        payload = await self.post_form("/oauth/token", {"grant_type": "refresh_token", "refresh_token": refresh_token})
        self._token_store.update(payload)


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:1000]

