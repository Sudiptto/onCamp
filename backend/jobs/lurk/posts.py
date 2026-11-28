"""Map a LurkAPI user-posts page into the media shape the existing post jobs already parse."""

from typing import Any

from app.services.lurk_client import USER_POSTS_PAGE_SIZE, LurkClient
from jobs.post_extraction.posts import extract_recent_posts


def lurk_posts_to_medias(payload: Any) -> dict[str, Any]:
    """Return `{items: [...]}` for extract_recent_posts / process_club_posts.

    Lurk already sends caption text and unix `taken_at`. Pinned posts can lead the
    page, so callers must still sort by timestamp instead of trusting list order.
    """
    posts = payload.get("posts") if isinstance(payload, dict) else None
    items: list[dict[str, Any]] = []
    for post in posts or []:
        if not isinstance(post, dict):
            continue
        images = post.get("images") or []
        image_url = post.get("display_url")
        if not image_url and images and isinstance(images[0], dict):
            image_url = images[0].get("url")
        items.append({
            "pk": post.get("pk"),
            "code": post.get("code") or "",
            "taken_at": post.get("taken_at"),
            "caption": post.get("caption") or "",
            "media_type": post.get("media_type"),
            "like_count": post.get("like_count"),
            "comment_count": post.get("comment_count"),
            "thumbnail_url": image_url,
            "permalink": post.get("url") or "",
            "user": post.get("user") if isinstance(post.get("user"), dict) else {},
        })
    return {
        "items": items,
        "provider": "lurkapi",
        "credits_charged": payload.get("credits_charged") if isinstance(payload, dict) else None,
        "credits_remaining": payload.get("credits_remaining") if isinstance(payload, dict) else None,
    }


def fetch_club_medias(
    client: LurkClient,
    username: str,
    page_size: int = USER_POSTS_PAGE_SIZE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch one user-posts page and adapt it. Always one credit, even for a single newest post."""
    raw = client.get_user_posts(username, first=page_size)
    return raw, lurk_posts_to_medias(raw)


def newest_posts(medias: dict[str, Any], count: int = 1) -> list[dict[str, Any]]:
    return extract_recent_posts(medias, count)
