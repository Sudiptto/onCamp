from typing import Any


def parse_activity_status(account: dict[str, Any]) -> str:
    """Return an activity state only when the payload provides a clear signal."""
    if account.get("is_disabled") is True or account.get("is_active") is False:
        return "inactive"
    if account.get("is_active") is True:
        return "active"
    if account.get("latest_post_at") or account.get("latest_reel_media"):
        return "active"
    return "unknown"


def add_activity_status(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {**account, "activity_status": parse_activity_status(account)}
        for account in accounts
    ]


def split_activity_status(
    accounts: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped = {"active": [], "inactive": [], "unknown": []}
    for account in accounts:
        grouped.setdefault(account["activity_status"], []).append(account)
    return grouped
