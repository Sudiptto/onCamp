from typing import Any

from jobs.activity_check.posts import _taken_at

DEFAULT_POST_COUNT = 3
MEDIA_TYPES = {1: "photo", 2: "video", 8: "carousel"}


def _caption_text(item: dict[str, Any]) -> str:
    caption = item.get("caption") or item.get("caption_text") or ""
    if isinstance(caption, dict):
        caption = caption.get("text") or ""
    return caption if isinstance(caption, str) else ""


def _image_url(item: dict[str, Any]) -> str | None:
    if isinstance(item.get("thumbnail_url"), str):
        return item["thumbnail_url"]
    candidates = (item.get("image_versions2") or {}).get("candidates") or []
    return candidates[0].get("url") if candidates and isinstance(candidates[0], dict) else None


def normalize_post(item: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the fields we care about out of one raw media item; None if it has no usable timestamp."""
    taken_at = _taken_at(item)
    if taken_at is None:
        return None
    code = item.get("code") or item.get("short_code") or ""
    media_type = item.get("media_type")
    return {
        "post_id": str(item.get("pk") or item.get("id") or ""),
        "post_code": code,
        "post_url": f"https://www.instagram.com/p/{code}/" if code else item.get("permalink") or "",
        "taken_at": taken_at.isoformat(),
        "media_type": MEDIA_TYPES.get(media_type, media_type),
        "caption": _caption_text(item),
        "image_url": _image_url(item),
        "like_count": item.get("like_count"),
        "comment_count": item.get("comment_count"),
    }


def extract_recent_posts(response: Any, count: int = DEFAULT_POST_COUNT) -> list[dict[str, Any]]:
    """Return the newest `count` posts (newest first) from a flat /gql/user/medias response."""
    items = response.get("items") if isinstance(response, dict) else None
    posts = [post for item in items or [] if isinstance(item, dict) and (post := normalize_post(item))]
    # Pinned posts can sit at the top of the grid, so sort by timestamp instead of trusting order.
    posts.sort(key=lambda post: post["taken_at"], reverse=True)
    return posts[:count]
