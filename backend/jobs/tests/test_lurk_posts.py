from jobs.lurk.pilot import append_usage, usage_row
from jobs.lurk.posts import lurk_posts_to_medias, newest_posts
from jobs.post_extraction.posts import extract_recent_posts


def _post(pk, code, taken_at, caption="hello", media_type=1):
    return {
        "pk": pk,
        "code": code,
        "taken_at": taken_at,
        "caption": caption,
        "media_type": media_type,
        "display_url": f"https://cdn.example/{code}.jpg",
        "url": f"https://www.instagram.com/p/{code}/",
        "like_count": 3,
        "comment_count": 1,
        "user": {"username": "hunter_bsa", "full_name": "Hunter BSA"},
    }


def test_adapter_feeds_existing_extractor_and_ignores_pinned_order():
    payload = {
        "success": True,
        "credits_charged": 1,
        "credits_remaining": 100,
        "posts": [
            _post("1", "OLD", 1_000, caption=None),
            _post("2", "NEW", 2_000, caption="mixer friday", media_type=8),
        ],
    }

    medias = lurk_posts_to_medias(payload)
    posts = extract_recent_posts(medias, count=1)

    assert medias["provider"] == "lurkapi"
    assert posts[0]["post_code"] == "NEW"
    assert posts[0]["caption"] == "mixer friday"
    assert posts[0]["image_url"] == "https://cdn.example/NEW.jpg"
    assert posts[0]["post_url"] == "https://www.instagram.com/p/NEW/"
    assert newest_posts(medias)[0]["post_id"] == "2"


def test_null_caption_and_missing_timestamp_are_safe():
    medias = lurk_posts_to_medias({
        "posts": [
            {"pk": "9", "code": "X", "caption": None, "taken_at": 50, "images": [{"url": "https://img"}]},
            {"code": "NOID"},
            "bad",
        ]
    })

    posts = extract_recent_posts(medias)
    assert posts[0]["caption"] == ""
    assert posts[0]["image_url"] == "https://img"
    assert len(posts) == 1


def test_empty_payload():
    assert lurk_posts_to_medias(None)["items"] == []
    assert newest_posts(lurk_posts_to_medias({"posts": []})) == []


def test_usage_row_marks_cache_and_tokens():
    row = usage_row({
        "fetched_at": "2026-03-28T00:00:00+00:00",
        "username": "hunter_bsa",
        "credits_charged": 0,
        "credits_remaining": 49999,
        "from_cache": True,
        "newest_post_code": "ABC",
        "analysis": {"details": {"is_event": False}, "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}},
    })
    assert "| hunter_bsa | 0 | 49999 | yes | 10 | 4 | 14 | ABC | not an event |" in row


def test_usage_rows_remain_contiguous(tmp_path):
    tracker = tmp_path / "ledger.md"
    tracker.write_text("<!-- usage-log -->\n| old |\n", encoding="utf-8")
    append_usage(tracker, ["| new |"])
    append_usage(tracker, ["| newest |"])
    assert tracker.read_text(encoding="utf-8") == (
        "<!-- usage-log -->\n| newest |\n| new |\n| old |\n"
    )
