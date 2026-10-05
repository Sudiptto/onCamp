from datetime import datetime, timezone
from typing import Any

# Instagram media IDs are snowflakes: (id >> 23) + this epoch (ms) is the upload time.
_INSTAGRAM_EPOCH_MS = 1314220021721


def _taken_at(item: dict[str, Any]) -> datetime | None:
    # HikerAPI's GraphQL payload prefixes some keys, so the field arrives as "1ltaken_at".
    raw = item.get("1ltaken_at") or item.get("taken_at")
    if isinstance(raw, (int, float)) and raw > 0:
        return datetime.fromtimestamp(raw, timezone.utc)
    try:
        millis = (int(item["pk"]) >> 23) + _INSTAGRAM_EPOCH_MS
    except (KeyError, TypeError, ValueError):
        return None
    return datetime.fromtimestamp(millis / 1000, timezone.utc)


def parse_latest_post(response: Any) -> dict[str, Any] | None:
    """Return the newest post from a flat /gql/user/medias response, or None if there are none."""
    items = response.get("items") if isinstance(response, dict) else None
    posts = []
    for item in items or []:
        taken_at = _taken_at(item) if isinstance(item, dict) else None
        if taken_at is not None:
            posts.append((taken_at, item))
    if not posts:
        return None

    # Pinned posts can sit at the top of the grid, so take the newest timestamp, not the first item.
    taken_at, item = max(posts, key=lambda pair: pair[0])
    return {
        "post_id": str(item.get("pk") or item.get("id") or ""),
        "post_code": item.get("code") or "",
        "taken_at": taken_at,
    }
