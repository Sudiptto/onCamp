from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import ArchivedEvent, Club, ClubActivity, ClubPostCheckpoint, Event
from app.services.event_archive import archive_past_events
from jobs.post_extraction.ai import ExtractionError, find_google_form_url, parse_extraction
from jobs.post_extraction.club_posts import (
    find_clubs_due_for_post_scan,
    process_club_posts,
    select_new_posts,
)
from seed_colleges import seed_colleges
from sync_clubs import sync_clubs

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)  # 8am campus time
FUTURE = datetime(2026, 10, 30, 18, 0)
PAST = datetime(2026, 10, 20, 18, 0)


def medias(*posts):
    return {"items": [
        {"pk": pk, "code": f"C{pk}", "1ltaken_at": ts, "caption": {"text": text}}
        for pk, ts, text in posts
    ]}


def fake_extractor(caption, posted_at, club_name, college_name):
    """'future'/'past' in the caption make an event on that side of NOW; 'undated' has no date."""
    is_event = any(word in caption for word in ("future", "past", "undated"))
    start = FUTURE if "future" in caption else PAST if "past" in caption else None
    return {
        "is_event": is_event, "title": caption[:20] if is_event else None, "description": None,
        "start_time": start, "end_time": None, "location": "HN 118" if is_event else None,
        "has_free_food": "pizza" in caption,
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


def test_only_upcoming_events_are_stored(club):
    raw = medias(
        ("1", 1000, "future event pizza https://forms.gle/z"),
        ("2", 2000, "past event"),
        ("3", 3000, "undated event"),
        ("4", 4000, "just a meme"),
    )
    result = process_club_posts(club, raw, 5, extractor=fake_extractor, now=NOW)

    assert result["processed"] == 4
    assert (result["past_events"], result["undated_events"], result["not_events"]) == (1, 1, 1)
    event = Event.query.one()
    assert event.post_id == "1" and event.start_time == FUTURE and event.is_free_food
    assert event.google_form_url == "https://forms.gle/z"
    assert event.source_url == "https://www.instagram.com/p/C1/"
    assert event.college_id == club.college_id
    assert ArchivedEvent.query.count() == 0


def test_second_run_does_not_recheck_posts(club):
    raw = medias(("1", 1000, "future event"), ("2", 2000, "just a meme"))
    assert process_club_posts(club, raw, 3, extractor=fake_extractor, now=NOW)["processed"] == 2

    calls = []

    def counting(*args):
        calls.append(args)
        return fake_extractor(*args)

    second = process_club_posts(club, raw, 3, extractor=counting, now=NOW)
    assert second["processed"] == 0 and second["already_checked"] == 2 and calls == []

    third = process_club_posts(club, medias(("3", 3000, "future event"), ("2", 2000, "x")), 3, extractor=counting, now=NOW)
    assert third["processed"] == 1 and len(calls) == 1

    checkpoint = ClubPostCheckpoint.query.one()
    assert checkpoint.last_post_id == "3"
    assert Event.query.count() == 2


def test_ai_failure_keeps_failed_post_for_retry(club):
    raw = medias(("1", 1000, "future event"), ("2", 2000, "future event"))

    def flaky(caption, posted_at, club_name, college_name):
        if posted_at.minute == 33:  # the second post, taken_at=2000s
            raise ExtractionError("boom")
        return fake_extractor(caption, posted_at, club_name, college_name)

    first_scan = NOW - timedelta(days=5)
    result = process_club_posts(club, raw, 3, extractor=flaky, now=first_scan)
    assert result["processed"] == 1 and "boom" in result["error"]
    assert ClubPostCheckpoint.query.one().last_post_id == "1"

    retry = process_club_posts(club, raw, 3, extractor=fake_extractor, now=NOW)
    assert retry["processed"] == 1 and retry["error"] is None


def test_empty_scan_still_records_checked_at(club):
    process_club_posts(club, {"items": []}, 3, extractor=fake_extractor, now=NOW)
    checkpoint = ClubPostCheckpoint.query.one()
    assert checkpoint.last_post_id is None
    assert checkpoint.checked_at == NOW.replace(tzinfo=None)


def test_due_for_post_scan_only_active_and_every_two_days(club):
    assert find_clubs_due_for_post_scan("hunter", now=NOW) == []  # no activity row yet

    db.session.add(ClubActivity(club_id=club.id, college_id=club.college_id, status="inactive"))
    db.session.commit()
    assert find_clubs_due_for_post_scan("hunter", now=NOW) == []

    ClubActivity.query.one().status = "active"
    db.session.commit()
    assert find_clubs_due_for_post_scan("hunter", now=NOW) == [club]  # never scanned

    process_club_posts(club, {"items": []}, 3, extractor=fake_extractor, now=NOW)
    assert find_clubs_due_for_post_scan("hunter", now=NOW + timedelta(days=1)) == []
    assert find_clubs_due_for_post_scan("hunter", now=NOW + timedelta(days=2)) == [club]


def test_archive_past_events_moves_finished_events(club):
    def add(post_id, start, end=None):
        db.session.add(Event(
            club_id=club.id, college_id=club.college_id, post_id=post_id,
            title=post_id, start_time=start, end_time=end,
        ))

    add("over", datetime(2026, 10, 26, 18, 0), datetime(2026, 10, 26, 20, 0))
    add("date-only-today", datetime(2026, 10, 27, 0, 0))  # no end: lasts all day
    add("date-only-yesterday", datetime(2026, 10, 26, 0, 0))
    add("upcoming", FUTURE)
    db.session.commit()

    assert archive_past_events(NOW) == 2
    assert {e.post_id for e in Event.query} == {"date-only-today", "upcoming"}
    assert {e.post_id for e in ArchivedEvent.query} == {"over", "date-only-yesterday"}
    assert archive_past_events(NOW) == 0
