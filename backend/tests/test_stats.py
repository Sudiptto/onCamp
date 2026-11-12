import time
from datetime import datetime, timedelta, timezone

import pytest

from app.api import stats
from app.extensions import db
from app.models import Club, Event, User
from app.services.event_archive import campus_now


@pytest.fixture(autouse=True)
def clear_stats_cache():
    stats._cache.update({"at": 0.0, "data": None})
    yield
    stats._cache.update({"at": 0.0, "data": None})


def make_user(i, email=None, sub=None, signed_in=True):
    return User(
        google_sub=sub or f"sub-{i}",
        email=email or f"user{i}@example.com",
        last_login_at=datetime.now(timezone.utc) if signed_in else None,
    )


def add_users(count, start=0):
    db.session.add_all([make_user(i) for i in range(start, start + count)])
    db.session.commit()


def milestone(client):
    return client.get("/api/stats").get_json()["users_milestone"]


def test_milestone_stays_close_to_the_real_number():
    assert stats.user_milestone(0) is None
    assert stats.user_milestone(99) is None
    assert stats.user_milestone(100) == 100
    assert stats.user_milestone(109) == 100
    assert stats.user_milestone(249) == 240
    assert stats.user_milestone(250) == 250
    assert stats.user_milestone(999) == 990
    assert stats.user_milestone(1000) == 1000
    assert stats.user_milestone(1234) == 1200
    assert stats.user_milestone(12300) == 12000
    assert stats.user_milestone(99999) == 99000
    assert stats.user_milestone(100000) == 100000


def test_milestone_never_understates_by_more_than_ten_percent():
    for count in list(range(100, 3000)) + [12300, 54321, 99999, 123456]:
        shown = stats.user_milestone(count)
        assert shown <= count
        assert shown >= count * 0.9


def test_nothing_shown_under_100_people(client):
    add_users(40)
    assert milestone(client) is None


def test_milestone_shows_close_to_the_real_number(client):
    add_users(120)
    assert milestone(client) == 120


def test_same_email_with_a_new_google_id_counts_once(client):
    add_users(99)
    db.session.add(make_user(500, email="user0@example.com", sub="recreated-account"))
    db.session.commit()
    assert milestone(client) is None  # 100 rows, but only 99 different people


def test_email_case_does_not_make_a_second_person(client):
    add_users(99)
    db.session.add(make_user(501, email="USER0@Example.com", sub="shouty-case"))
    db.session.commit()
    assert milestone(client) is None


def test_rows_that_never_signed_in_do_not_count(client):
    add_users(99)
    db.session.add_all([make_user(600 + i, signed_in=False) for i in range(5)])
    db.session.commit()
    assert milestone(client) is None


def test_team_and_test_accounts_can_be_excluded(app, client):
    app.config["STATS_EXCLUDED_EMAILS"] = "team1@example.com, TEAM2@example.com"
    add_users(98)
    db.session.add_all([
        make_user(700, email="team1@example.com"),
        make_user(701, email="team2@example.com"),
    ])
    db.session.commit()
    assert milestone(client) is None  # 100 rows, 98 counted


def test_stats_never_expose_exact_counts_or_user_data(client):
    add_users(120)
    body = client.get("/api/stats").get_json()
    assert set(body) == {"users_milestone", "clubs", "upcoming_events"}
    assert "user0@example.com" not in str(body)


def test_query_parameters_cannot_change_the_numbers(client):
    add_users(120)
    plain = client.get("/api/stats").get_json()
    tricked = client.get("/api/stats?users=99999&users_milestone=5000&clubs=7").get_json()
    assert plain == tricked


def test_counts_active_clubs_and_upcoming_events_only(client):
    db.session.add_all([
        Club(college_id=1, name="Active", instagram_handle="active", is_active=True),
        Club(college_id=1, name="Inactive", instagram_handle="inactive", is_active=False),
    ])
    db.session.commit()
    club_id = Club.query.filter_by(instagram_handle="active").one().id
    now = campus_now()

    def event(title, start, post_id):
        return Event(club_id=club_id, college_id=1, title=title, start_time=start, post_id=post_id)

    db.session.add_all([
        event("Past", now - timedelta(days=2), "post-1"),
        event("An hour ago", now - timedelta(hours=1), "post-2"),
        event("Soon", now + timedelta(days=2), "post-3"),
        event("No date", None, "post-4"),
    ])
    db.session.commit()

    body = client.get("/api/stats").get_json()
    assert body["clubs"] == 1
    assert body["upcoming_events"] == 1


def test_stats_are_cached_for_a_while(client):
    add_users(120)
    assert milestone(client) == 120
    add_users(200, start=1000)
    assert milestone(client) == 120  # cached, not 320


def test_database_failure_with_no_cache_returns_safe_empty_values(client, monkeypatch):
    def boom():
        raise RuntimeError("database is down")

    monkeypatch.setattr(stats, "_build_stats", boom)
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert response.get_json() == stats.EMPTY


def test_database_failure_keeps_showing_the_last_good_numbers(client, monkeypatch):
    stats._cache.update({
        "at": time.monotonic() - 10_000,
        "data": {"users_milestone": 250, "clubs": 12, "upcoming_events": 40},
    })

    def boom():
        raise RuntimeError("database is down")

    monkeypatch.setattr(stats, "_build_stats", boom)
    assert client.get("/api/stats").get_json()["users_milestone"] == 250


def test_stats_work_without_signing_in(client):
    assert client.get("/api/stats").status_code == 200
