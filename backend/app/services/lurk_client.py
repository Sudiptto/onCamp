import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

# Invalid params, auth, empty balance, and rate limits are rejected before the
# platform is checked, so they are free. 5xx is also free. 404 is charged.
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
MAX_RETRIES = 2
RETRY_BASE_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 30.0
DEFAULT_BASE_URL = "https://api.lurkapi.com"
USER_POSTS_PATH = "/v2/instagram/user/posts"
# Instagram returns at most 12 posts per page. A larger `first` still costs 1 credit.
USER_POSTS_PAGE_SIZE = 12


class LurkAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _retry_delay(response: requests.Response | None, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_DELAY_SECONDS)
        except ValueError:
            pass
    return min(RETRY_BASE_DELAY_SECONDS * 2**attempt, MAX_RETRY_DELAY_SECONDS)


def _read_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


class LurkClient:
    """Thin GET client for LurkAPI. Post scans only need user posts (1 credit)."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("LURK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        if api_key is None:
            api_key = os.getenv("LURK_API_KEY") or os.getenv("LURKAPI_API_KEY")
        self.api_key = api_key
        self.calls: list[dict[str, Any]] = []

    @property
    def credits_charged(self) -> int:
        return sum(int(call.get("credits_charged") or 0) for call in self.calls)

    @property
    def credits_remaining(self) -> int | None:
        for call in reversed(self.calls):
            remaining = call.get("credits_remaining")
            if remaining is not None:
                return int(remaining)
        return None

    @property
    def headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key or "", "accept": "application/json"}

    def _record(self, path: str, body: Any, status_code: int | None) -> None:
        charged = remaining = None
        code = None
        if isinstance(body, dict):
            charged = body.get("credits_charged")
            remaining = body.get("credits_remaining")
            code = body.get("code")
        try:
            charged_n = int(charged) if charged is not None else None
        except (TypeError, ValueError):
            charged_n = None
        try:
            remaining_n = int(remaining) if remaining is not None else None
        except (TypeError, ValueError):
            remaining_n = None
        self.calls.append({
            "path": path,
            "status_code": status_code,
            "code": code,
            "credits_charged": charged_n,
            "credits_remaining": remaining_n,
        })

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise LurkAPIError("Missing LURK_API_KEY. Add it to the project .env file.")

        last_error: LurkAPIError | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.get(
                    f"{self.base_url}{path}",
                    params=params or {},
                    headers=self.headers,
                    timeout=60,
                )
            except requests.RequestException as exc:
                raise LurkAPIError(f"LurkAPI request failed for {path}: {exc}") from exc

            body = _read_json(response)
            if response.status_code >= 400:
                self._record(path, body, response.status_code)
                code = body.get("code") if isinstance(body, dict) else None
                detail = body.get("error") if isinstance(body, dict) else response.text[:300]
                last_error = LurkAPIError(
                    f"LurkAPI request failed for {path} ({response.status_code} {code or 'error'}): {detail}",
                    status_code=response.status_code,
                    code=str(code) if code else None,
                )
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                    time.sleep(_retry_delay(response, attempt))
                    continue
                raise last_error

            if isinstance(body, dict) and body.get("success") is False:
                self._record(path, body, response.status_code)
                raise LurkAPIError(
                    f"LurkAPI request failed for {path}: {body.get('error') or body.get('code')}",
                    status_code=response.status_code,
                    code=str(body.get("code") or "") or None,
                )
            self._record(path, body, response.status_code)
            return body
        raise last_error or LurkAPIError(f"LurkAPI request failed for {path}")

    def get_user_posts(self, username: str, first: int = USER_POSTS_PAGE_SIZE) -> dict[str, Any]:
        """One page of public posts. Captions are included, so a post-detail call is unnecessary."""
        handle = username.strip().lstrip("@")
        if not handle:
            raise LurkAPIError("Instagram username is required.", code="invalid_params")
        page_size = min(max(int(first), 1), 50)
        data = self.get(USER_POSTS_PATH, {"username": handle, "first": page_size})
        if not isinstance(data, dict) or data.get("success") is not True or not isinstance(data.get("posts"), list):
            raise LurkAPIError(f"LurkAPI user posts for @{handle} had an invalid response.")
        return data
