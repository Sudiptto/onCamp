from datetime import datetime, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import Club, ClubPost, ClubPostCheckpoint
from jobs.post_extraction.ai import ExtractionError, find_google_form_url, parse_extraction
from jobs.post_extraction.club_posts import process_club_posts, select_new_posts
from seed_colleges import seed_colleges
from sync_clubs import sync_clubs

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def medias(*posts):
    return {"items": [
        {"pk": pk, "code": f"C{pk}", "1ltaken_at": ts, "caption": {"text": text}}
        for pk, ts, text in posts
    ]}


def fake_extractor(caption, posted_at, club_name, college_name):
    return {
        "is_event": "event" in caption, "title": caption[:20], "description": None,
        "start_time": None, "end_time": None, "location": None, "has_free_food": "pizza" in caption,
    }


@pytest.fixture
def club():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite://", "TESTING": True, "RATELIMIT_ENABLED": False})
    with app.app_context():
        seed_colleges()
        sync_clubs([{"username": "hunter_bsa", "user_id": "1", "full_name": "Hunter BSA"}], "hunter")
        yield Club.query.first()


def test_find_google_form_url():
    assert find_google_form_url("RSVP: https://forms.gle/abc123.") == "https://forms.gle/abc123"
    assert find_google_form_url("https://docs.google.com/forms/d/e/xyz/viewform?usp=sf") is not None
    assert find_google_form_url("link in bio") is None


def test_parse_extraction_valid_and_bad_times():
    result = parse_extraction(
        '{"is_event": true, "title": "Mixer", "start_time": "2026-11-01T18:00:00",'
        ' "end_time": "2026-11-01T17:00:00", "location": "HN 118", "has_free_food": true}'
    )
    assert result["start_time"] == datetime(2026, 11, 1, 18, 0)
    assert result["end_time"] is None  # ends before it starts
    assert result["has_free_food"] is True


@pytest.mark.parametrize("content", ["not json", "[]", '{"title": "x"}', '{"is_event": "yes"}'])
def test_parse_extraction_rejects_bad_output(content):
    with pytest.raises(ExtractionError):
        parse_extraction(content)


def test_select_new_posts_skips_seen_and_old():
    posts = [
        {"post_id": "3", "taken_at": "2026-10-03T00:00:00+00:00"},
        {"post_id": "2", "taken_at": "2026-10-02T00:00:00+00:00"},
        {"post_id": "1", "taken_at": "2026-10-01T00:00:00+00:00"},
    ]
    new = select_new_posts(posts, datetime(2026, 10, 1, 12), {"3"})
    assert [p["post_id"] for p in new] == ["2"]
    assert [p["post_id"] for p in select_new_posts(posts, None, set())] == ["1", "2", "3"]


def test_second_run_does_not_recheck_posts(club):
    raw = medias(("1", 1000, "event pizza https://forms.gle/z"), ("2", 2000, "just a meme"))
    first = process_club_posts(club, raw, 3, extractor=fake_extractor, now=NOW)
    assert first["processed"] == 2

    calls = []
    def counting(*args):
        calls.append(args)
        return fake_extractor(*args)

    second = process_club_posts(club, raw, 3, extractor=counting, now=NOW)
    assert second["processed"] == 0 and second["already_checked"] == 2 and calls == []

    third = process_club_posts(club, medias(("3", 3000, "event"), *[("2", 2000, "x")]), 3, extractor=counting, now=NOW)
    assert third["processed"] == 1 and len(calls) == 1

    checkpoint = ClubPostCheckpoint.query.one()
    assert checkpoint.last_post_id == "3"
    row = ClubPost.query.filter_by(post_id="1").one()
    assert row.has_free_food and row.google_form_url == "https://forms.gle/z"
    assert row.post_url == "https://www.instagram.com/p/C1/"


def test_ai_failure_keeps_failed_post_for_retry(club):
    raw = medias(("1", 1000, "event"), ("2", 2000, "event"))

    def flaky(caption, posted_at, club_name, college_name):
        if posted_at.year == 1970 and posted_at.minute == 33:  # the second post, taken_at=2000s
            raise ExtractionError("boom")
        return fake_extractor(caption, posted_at, club_name, college_name)

    result = process_club_posts(club, raw, 3, extractor=flaky, now=NOW)
    assert result["processed"] == 1 and "boom" in result["error"]
    assert ClubPostCheckpoint.query.one().last_post_id == "1"

    retry = process_club_posts(club, raw, 3, extractor=fake_extractor, now=NOW)
    assert retry["processed"] == 1 and retry["error"] is None
