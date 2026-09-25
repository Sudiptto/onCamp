from typing import Any


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def normalize_account(account: dict[str, Any]) -> dict[str, Any]:
    user_id = account.get("pk") or account.get("id") or account.get("user_id")
    return {
        "username": _normalize_text(account.get("username")),
        "user_id": str(user_id),
        "full_name": _normalize_text(account.get("full_name") or account.get("name")),
        "profile_pic_url": _normalize_text(
            account.get("profile_pic_url") or account.get("profile_picture") or ""
        ),
        "is_private": bool(account.get("is_private") or False),
    }


def extract_public_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        normalized
        for normalized in (normalize_account(account) for account in accounts)
        if not normalized["is_private"]
    ]
