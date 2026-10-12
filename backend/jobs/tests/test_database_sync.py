from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import Club, ClubActivity
from run_due_activity_checks import count_clubs_missing_user_id, find_due_clubs
from seed_colleges import seed_colleges
from sync_club_activity import sync_club_activity
from sync_clubs import sync_clubs

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def app():
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "TESTING": True,
        "RATELIMIT_ENABLED": False,
    })
    with app.app_context():
        seed_colleges()
        yield app


def club_record(handle, user_id=None, **extra):
    return {"username": handle, "user_id": user_id, "full_name": handle.title(), **extra}


def activity_record(user_id, handle, status="active", days_until_next=1):
    return {
        "user_id": user_id,
        "username": handle,
        "status": status,
        "last_post_id": "post-1",
        "last_post_at": "2026-10-01T00:00:00+00:00",
        "next_check_at": (NOW + timedelta(days=days_until_next)).isoformat(),
    }


# sync_clubs

def test_sync_clubs_saves_user_id_and_picture(app):
    summary = sync_clubs(
        [club_record("coding", "111", profile_pic_url="https://img/1.jpg")], "hunter"
    )

    club = Club.query.one()
    assert summary == {"created": 1, "updated": 0, "skipped": 0}
    assert (club.instagram_user_id, club.profile_pic_url) == ("111", "https://img/1.jpg")


def test_sync_clubs_is_idempotent(app):
    sync_clubs([club_record("coding", "111")], "hunter")
    summary = sync_clubs([club_record("coding", "111", full_name="Coding Club")], "hunter")

    assert summary["updated"] == 1
    assert Club.query.count() == 1
    assert Club.query.one().name == "Coding Club"


def test_sync_clubs_matches_renamed_handle_by_user_id(app):
    sync_clubs([club_record("old_name", "111")], "hunter")
    sync_clubs([club_record("new_name", "111")], "hunter")

    assert Club.query.count() == 1
    assert Club.query.one().instagram_handle == "new_name"


def test_sync_clubs_keeps_is_active(app):
    sync_clubs([club_record("coding", "111")], "hunter")
    club = Club.query.one()
    club.is_active = False
    db.session.commit()

    sync_clubs([club_record("coding", "111")], "hunter")

    assert Club.query.one().is_active is False


def test_sync_clubs_skips_missing_handle(app):
    summary = sync_clubs([{"username": "", "user_id": "9"}], "hunter")
    assert summary["skipped"] == 1
    assert Club.query.count() == 0


def test_sync_clubs_requires_college(app):
    with pytest.raises(ValueError, match="seed_colleges"):
        sync_clubs([club_record("coding", "111")], "nowhere")


# sync_club_activity

def test_sync_club_activity_saves_status(app):
    sync_clubs([club_record("busy", "1"), club_record("quiet", "2")], "hunter")

    summary = sync_club_activity([
        activity_record("1", "busy", "active", 1),
        activity_record("2", "quiet", "inactive", 30),
    ], now=NOW)

    assert summary["matched"] == 2
    assert Club.query.filter_by(instagram_handle="busy").one().is_active is True
    assert Club.query.filter_by(instagram_handle="quiet").one().is_active is False
    quiet = ClubActivity.query.join(Club).filter(Club.instagram_handle == "quiet").one()
    assert quiet.next_check_at == datetime(2026, 11, 5, 12, 0)


def test_sync_club_activity_is_idempotent(app):
    sync_clubs([club_record("busy", "1")], "hunter")
    for _ in range(2):
        sync_club_activity([activity_record("1", "busy")], now=NOW)

    assert ClubActivity.query.count() == 1


def test_sync_club_activity_backs_off_missing_account(app):
    sync_clubs([club_record("gone", "1")], "hunter")
    sync_club_activity([activity_record("1", "gone")], now=NOW)

    summary = sync_club_activity([], now=NOW, errors=[
        {"user_id": "1", "username": "gone", "status_code": 404},
    ])

    activity = ClubActivity.query.one()
    assert summary["backed_off"] == 1
    assert activity.status == "error"
    assert activity.next_check_at == datetime(2026, 11, 5, 12, 0)
    assert activity.last_post_id == "post-1"
    assert Club.query.one().is_active is True


@pytest.mark.parametrize("status_code", [429, 500, 503, None])
def test_sync_club_activity_ignores_temporary_errors(app, status_code):
    sync_clubs([club_record("fine", "1")], "hunter")

    summary = sync_club_activity([], now=NOW, errors=[
        {"user_id": "1", "username": "fine", "status_code": status_code},
    ])

    assert summary["will_retry"] == 1
    assert ClubActivity.query.count() == 0
    assert [c["username"] for c in find_due_clubs("hunter", now=NOW)] == ["fine"]


def test_sync_club_activity_counts_unknown_club(app):
    summary = sync_club_activity([activity_record("404", "stranger")], now=NOW)
    assert summary["unmatched"] == 1


# find_due_clubs

def test_find_due_clubs_new_or_overdue(app):
    sync_clubs([club_record(name, str(i)) for i, name in
                enumerate(["new", "overdue", "boundary", "later"], start=1)], "hunter")
    sync_club_activity([
        activity_record("2", "overdue", days_until_next=-1),
        activity_record("3", "boundary", days_until_next=0),
        activity_record("4", "later", days_until_next=1),
    ], now=NOW)

    due = [club["username"] for club in find_due_clubs("hunter", now=NOW)]

    assert due == ["new", "overdue", "boundary"]


def test_find_due_clubs_uses_user_id(app):
    sync_clubs([club_record("coding", "12345")], "hunter")
    assert find_due_clubs("hunter", now=NOW) == [{"user_id": "12345", "username": "coding"}]


def test_find_due_clubs_skips_missing_user_id(app):
    sync_clubs([club_record("no_id", None), club_record("has_id", "7")], "hunter")

    assert [c["username"] for c in find_due_clubs("hunter", now=NOW)] == ["has_id"]
    assert count_clubs_missing_user_id("hunter") == 1


def test_find_due_clubs_unknown_college(app):
    with pytest.raises(ValueError):
        find_due_clubs("typo", now=NOW)


# the public API

def test_api_rate_limit_returns_429():
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "TESTING": True,
        "RATELIMIT_DEFAULT": "3 per minute",
    })
    client = app.test_client()

    statuses = [client.get("/api/health").status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]
    assert "error" in client.get("/api/health").get_json()


def test_cors_allows_only_frontend():
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "TESTING": True,
        "RATELIMIT_ENABLED": False,
    })
    client = app.test_client()

    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    blocked = client.get("/api/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in blocked.headers
