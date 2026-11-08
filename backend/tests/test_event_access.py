from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import ArchivedEvent, Club, College, Event, User
from app.services.event_archive import archive_past_events
from jobs.post_extraction.club_posts import process_club_posts
from tests.helpers import sign_in

NOW = datetime(2026, 10, 27, 8)
UTC_NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def events(app, monkeypatch):
    monkeypatch.setattr("app.api.routes.campus_now", lambda: NOW)
    monkeypatch.setattr("app.services.calendar_events.campus_now", lambda now=None: NOW)
    college = College(key="hunter", name="Hunter", seed_account="hunterusg")
    db.session.add(college)
    db.session.flush()
    coding = Club(college_id=college.id, name="Coding Club", instagram_handle="coding")
    dance = Club(college_id=college.id, name="Dance Club", instagram_handle="dance")
    db.session.add_all([coding, dance])
    db.session.flush()

    def add_event(post_id, club, days, **values):
        start = (NOW + timedelta(days=days)).replace(hour=18)
        db.session.add(Event(
            college_id=college.id,
            club_id=club.id,
            post_id=post_id,
            title=post_id,
            start_time=start,
            **values,
        ))

    add_event("one", coding, 1, end_time=(NOW + timedelta(days=1)).replace(hour=20),
              location="Room 1", is_free_food=True, source_url="https://instagram.com/p/one/")
    add_event("two", dance, 6)
    add_event("three", coding, 10)
    add_event("four", dance, 24)
    add_event("ongoing", coding, 0, end_time=NOW + timedelta(hours=1))
    add_event("finished", coding, 0, end_time=NOW - timedelta(hours=1))
    add_event("old-live", coding, -3)
    db.session.add(ArchivedEvent(
        college_id=college.id, club_id=dance.id, post_id="old-archived",
        title="old-archived", start_time=NOW - timedelta(days=20), archived_at=NOW,
    ))
    db.session.add(ArchivedEvent(
        college_id=college.id, club_id=dance.id, post_id="too-old",
        title="too-old", start_time=NOW - timedelta(days=121), archived_at=NOW,
    ))
    db.session.add(Event(college_id=college.id, club_id=coding.id, title="Undated"))
    db.session.commit()
    return {"coding": coding.id, "dance": dance.id}


def test_signed_out_visitors_receive_database_events_and_week_limit(client, events):
    response = client.get("/api/events")
    body = response.get_json()

    assert response.status_code == 200
    assert [event["event_id"] for event in body["events"]] == ["post:ongoing", "post:one", "post:two"]
    assert body["count"] == 3
    assert body["limited"] is True
    assert body["locked_count"] == 2
    event = body["events"][1]
    assert event == {
        "event_id": "post:one", "club_id": str(events["coding"]), "club_name": "Coding Club",
        "club_link": "https://www.instagram.com/coding/", "club_pfp": None, "event_name": "one",
        "event_link": None, "free_food": True, "date": "2026-10-28", "start_time": "18:00",
        "end_time": "20:00", "start_datetime": "2026-10-28T18:00:00",
        "location": "Room 1", "post_link": "https://instagram.com/p/one/",
    }


def test_range_and_club_filters_respect_access_limit(client, events):
    for range_key in ("2w", "1m", "semester", "all"):
        body = client.get(f"/api/events/filter?range={range_key}").get_json()
        assert all(event["date"] <= "2026-11-03" for event in body["events"])
    body = client.get(f"/api/events/filter?range=all&club_id={events['coding']}").get_json()
    assert [event["event_id"] for event in body["events"]] == ["post:ongoing", "post:one"]
    assert body["locked_count"] == 1


def test_empty_database_returns_an_empty_calendar(client):
    Event.query.delete()
    ArchivedEvent.query.delete()
    db.session.commit()
    body = client.get("/api/events").get_json()
    assert body["events"] == []
    assert body["count"] == 0
    assert body["limited"] is False


def test_date_only_event_is_visible_for_its_entire_day(client, events):
    college_id = db.session.get(Club, events["coding"]).college_id
    db.session.add_all([
        Event(club_id=events["coding"], college_id=college_id, post_id="today",
              title="Today", start_time=NOW.replace(hour=0)),
        Event(club_id=events["coding"], college_id=college_id, post_id="yesterday",
              title="Yesterday", start_time=NOW.replace(hour=0) - timedelta(days=1)),
    ])
    db.session.commit()
    ids = {event["event_id"] for event in client.get("/api/events").get_json()["events"]}
    assert "post:today" in ids
    assert "post:yesterday" not in ids


def test_signed_in_range_filters_and_order(client, monkeypatch):
    sign_in(client, monkeypatch)
    all_events = client.get("/api/events").get_json()
    assert [event["event_id"] for event in all_events["events"]] == [
        "post:ongoing", "post:one", "post:two", "post:three", "post:four",
    ]
    assert all_events["limited"] is False
    assert all_events["locked_count"] == 0
    assert client.get("/api/events/filter?range=1w").get_json()["count"] == 3
    assert client.get("/api/events/filter?range=2w").get_json()["count"] == 4
    assert client.get("/api/events/filter?range=1m").get_json()["count"] == 5


def test_archive_requires_login_and_includes_live_and_archived_events(client, monkeypatch, events):
    response = client.get("/api/events/archive")
    assert response.status_code == 401
    assert response.get_json()["code"] == "login_required"

    sign_in(client, monkeypatch)
    body = client.get("/api/events/archive").get_json()
    ids = {event["event_id"] for event in body["events"]}
    assert ids == {"post:old-archived", "post:old-live", "post:finished", "post:ongoing",
                   "post:one", "post:two", "post:three", "post:four"}
    body = client.get(f"/api/events/archive?club_id={events['dance']}").get_json()
    assert {event["event_id"] for event in body["events"]} == {
        "post:old-archived", "post:two", "post:four",
    }


def test_event_id_survives_archiving(client, monkeypatch):
    sign_in(client, monkeypatch)
    assert "post:old-live" in {e["event_id"] for e in client.get("/api/events/archive").get_json()["events"]}
    archive_past_events(UTC_NOW)
    assert "post:old-live" in {e["event_id"] for e in client.get("/api/events/archive").get_json()["events"]}


def test_extracted_event_reaches_calendar_api(client, events):
    club = db.session.get(Club, events["coding"])
    raw = {"items": [{
        "pk": "new-post", "code": "new-code", "taken_at": 1793090000,
        "caption": {"text": "Pizza party"},
    }]}

    def extractor(caption, posted_at, club_name, college_name):
        return {
            "is_event": True, "title": caption, "description": None,
            "start_time": NOW + timedelta(days=2), "end_time": None,
            "location": None, "has_free_food": True,
        }

    result = process_club_posts(club, raw, 3, extractor=extractor, now=UTC_NOW)
    assert len(result["events"]) == 1
    displayed = next(e for e in client.get("/api/events").get_json()["events"]
                     if e["event_id"] == "post:new-post")
    assert displayed["event_name"] == "Pizza party"
    assert displayed["free_food"] is True
    assert displayed["end_time"] is None
    assert displayed["post_link"] == "https://www.instagram.com/p/new-code/"


def test_deleted_account_loses_access_immediately(client, app, monkeypatch):
    sign_in(client, monkeypatch)
    assert client.get("/api/events/archive").status_code == 200
    db.session.delete(User.query.one())
    db.session.commit()
    assert client.get("/api/events/archive").status_code == 401
    assert client.get("/api/events").get_json()["limited"] is True


def test_invalid_filters_return_400(client, monkeypatch):
    assert client.get("/api/events/filter?range=bogus").status_code == 400
    for value in ("invalid", "-1", "0", "9999999999"):
        assert client.get(f"/api/events/filter?club_id={value}").status_code == 400
    sign_in(client, monkeypatch)
    assert client.get("/api/events/archive?club_id=invalid").status_code == 400


def test_event_responses_vary_by_cookie(client):
    response = client.get("/api/events")
    assert "Cookie" in response.headers["Vary"]
    assert "private" in response.headers["Cache-Control"]
