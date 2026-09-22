import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))


class HikerAPIError(RuntimeError):
    pass


class HikerClient:
    def __init__(
        self,
        base_url: str | None = None,
        access_key: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("HIKER_BASE_URL") or "https://api.instagrapi.com").rstrip("/")
        self.access_key = access_key or os.getenv("HIKERAPI_ACCESS_KEY") or os.getenv("HIKER_API_KEY")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "x-access-key": self.access_key or "",
            "accept": "application/json",
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.access_key:
            raise HikerAPIError("Missing HIKERAPI_ACCESS_KEY. Add it to the project .env file.")

        try:
            response = requests.get(
                f"{self.base_url}{path}",
                params=params or {},
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            detail = exc.response.text[:300] if exc.response is not None else str(exc)
            raise HikerAPIError(f"HikerAPI request failed for {path} ({status}): {detail}") from exc
        except requests.RequestException as exc:
            raise HikerAPIError(f"HikerAPI request failed for {path}: {exc}") from exc

    def check_balance(self) -> Any:
        return self.get("/sys/balance")

    def resolve_user(self, username: str) -> dict[str, Any]:
        data = self.get("/v2/user/by/username", {"username": username})
        return data.get("user") or data.get("data") or data

    def get_following(
        self,
        user_id: str | int,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Collect the full public follow graph for a seed account.

        HikerAPI returns paginated results, so we keep walking the follow list until
        the API stops returning a next-page token. This is intentionally broad and
        should be scheduled as a refresh job every few months, not as a live per-user
        action in the app.
        """
        endpoint = os.getenv("HIKER_FOLLOWING_ENDPOINT", "/gql/user/following/chunk")
        requested_page_size = page_size or int(os.getenv("HIKER_PAGE_SIZE", "50"))
        page_limit = max_pages or int(os.getenv("HIKER_MAX_PAGES", "25"))
        all_users: list[dict[str, Any]] = []
        seen_accounts: set[str] = set()
        page_token: str | None = None
        seen_tokens: set[str] = set()
        pages_fetched = 0

        for _ in range(page_limit):
            params: dict[str, Any] = {"user_id": user_id}
            if page_token:
                if endpoint.startswith("/gql/"):
                    params["end_cursor"] = page_token
                else:
                    params["page_id"] = page_token
            if endpoint == "/gql/user/following/chunk":
                params["force"] = os.getenv("HIKER_FOLLOWING_FORCE", "true").lower()
            elif endpoint.startswith("/g2/"):
                params["count"] = requested_page_size

            data = self.get(endpoint, params)
            pages_fetched += 1
            response = data.get("response") if isinstance(data, dict) else {}
            users: list[dict[str, Any]] = []

            if endpoint.startswith("/gql/") and isinstance(data, list):
                users = data[0] if data and isinstance(data[0], list) else []
            elif isinstance(response, dict):
                users = response.get("users") or response.get("edges") or []
            elif isinstance(data, dict):
                users = data.get("users") or data.get("data") or []

            if isinstance(users, dict):
                users = users.get("users") or users.get("data") or []

            if isinstance(users, list):
                for account in users:
                    account_key = str(account.get("pk") or account.get("id") or account.get("username") or "")
                    if account_key and account_key in seen_accounts:
                        continue
                    if account_key:
                        seen_accounts.add(account_key)
                    all_users.append(account)

            if endpoint.startswith("/gql/") and isinstance(data, list):
                next_token = data[1] if len(data) > 1 and isinstance(data[1], str) else None
            else:
                next_token = data.get("next_page_id") or (response.get("next_max_id") if isinstance(response, dict) else None)
            if not next_token:
                break

            next_token = str(next_token)
            if next_token in seen_tokens:
                break
            seen_tokens.add(next_token)
            page_token = next_token

            if isinstance(response, dict) and response.get("has_more") is False and data.get("has_more") is False:
                break

        return all_users, {
            "endpoint": endpoint,
            "pages_fetched": pages_fetched,
            "requested_page_size": requested_page_size,
            "raw_accounts": len(all_users),
        }
