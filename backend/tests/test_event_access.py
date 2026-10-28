from datetime import date, timedelta

from app.models import User
from tests.helpers import sign_in

# Numbers come from mock_events.py: events 1, 2, 4, 6 days out are in the free week,
# and 10, 13, 24, 45, 80 days out are locked. Past events only show in the archive.
FREE = 4
LOCKED = 5
ALL_UPCOMING = FREE + LOCKED


def _cutoff():
    return (date.today() + timedelta(days=7)).isoformat()


def test_signed_out_visitors_only_receive_the_first_week(client):
    body = client.get("/api/events").get_json()

    assert body["count"] == FREE
    assert body["limited"] is True
    assert body["locked_count"] == LOCKED
    assert all(event["date"] <= _cutoff() for event in body["events"])


def test_range_filter_cannot_get_around_the_cap(client):
    for range_key in ("2w", "1m", "semester", "all"):
        body = client.get(f"/api/events/filter?range={range_key}").get_json()
        assert all(event["date"] <= _cutoff() for event in body["events"]), range_key


def test_club_filter_cannot_get_around_the_cap(client):
    body = client.get("/api/events/filter?range=all&club_id=club_001").get_json()
    assert [event["event_id"] for event in body["events"]] == ["evt_001"]
    assert body["locked_count"] == 2


def test_signed_in_users_see_everything_upcoming(client, monkeypatch):
    sign_in(client, monkeypatch)
    body = client.get("/api/events").get_json()

    assert body["count"] == ALL_UPCOMING
    assert body["limited"] is False
    assert body["locked_count"] == 0


def test_archive_requires_sign_in(client, monkeypatch):
    response = client.get("/api/events/archive")
    assert response.status_code == 401
    assert response.get_json()["code"] == "login_required"

    sign_in(client, monkeypatch)
    response = client.get("/api/events/archive")
    assert response.status_code == 200
    assert response.get_json()["count"] == 13


def test_deleted_account_loses_access_immediately(client, app, monkeypatch):
    sign_in(client, monkeypatch)
    assert client.get("/api/events/archive").status_code == 200

    with app.app_context():
        from app.extensions import db

        db.session.delete(User.query.one())
        db.session.commit()

    assert client.get("/api/events/archive").status_code == 401
    assert client.get("/api/events").get_json()["limited"] is True


def test_invalid_range_still_returns_400(client):
    assert client.get("/api/events/filter?range=bogus").status_code == 400


def test_event_responses_vary_by_cookie(client):
    response = client.get("/api/events")
    assert "Cookie" in response.headers["Vary"]
    assert "private" in response.headers["Cache-Control"]
