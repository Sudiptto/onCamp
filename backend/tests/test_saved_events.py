from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import Club, College, Event, SavedEvent
from app.services.event_archive import archive_past_events
from tests.helpers import csrf_headers, sign_in

SOON = datetime(2030, 3, 4, 17, 0)  # far enough ahead to stay "upcoming"


@pytest.fixture()
def events(app):
    college = College(key="hunter", name="Hunter College", seed_account="hunterusg")
    db.session.add(college)
    db.session.flush()
    club = Club(college_id=college.id, name="Hunter Coding Club", instagram_handle="hunter_coding")
    db.session.add(club)
    db.session.flush()

    def make(post_id, start):
        event = Event(club_id=club.id, college_id=college.id, post_id=post_id, title=post_id, start_time=start)
        db.session.add(event)
        return event

    rows = [make("later", SOON + timedelta(days=3)), make("sooner", SOON)]
    db.session.commit()
    return {event.title: event.id for event in rows}


def save(client, event_id, headers=None):
    return client.post(
        "/api/saved-events",
        json={"event_id": event_id},
        headers=headers if headers is not None else csrf_headers(client),
    )


def unsave(client, event_id, headers=None):
    return client.delete(
        f"/api/saved-events/{event_id}",
        headers=headers if headers is not None else csrf_headers(client),
    )


def saved_ids(client):
    response = client.get("/api/saved-events")
    assert response.status_code == 200
    return [row["event_id"] for row in response.get_json()["saved_events"]]


def test_signed_out_visitors_are_refused(client, events):
    assert client.get("/api/saved-events").status_code == 401
    assert save(client, events["sooner"]).status_code == 401
    assert unsave(client, events["sooner"]).status_code == 401
    assert SavedEvent.query.count() == 0


def test_changes_need_the_csrf_header(client, monkeypatch, events):
    sign_in(client, monkeypatch)
    assert save(client, events["sooner"], headers={}).status_code == 403
    assert save(client, events["sooner"], headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert unsave(client, events["sooner"], headers={}).status_code == 403
    assert SavedEvent.query.count() == 0


def test_save_list_and_unsave(client, monkeypatch, events):
    sign_in(client, monkeypatch)

    first = save(client, events["later"])
    assert first.status_code == 201
    body = first.get_json()
    assert body["created"] is True
    assert body["saved"]["event"]["title"] == "later"
    assert body["saved"]["saved_at"]
    assert first.headers["Cache-Control"] == "private, no-store"

    assert save(client, events["sooner"]).status_code == 201
    # soonest event first, no matter the order they were saved in
    assert saved_ids(client) == [events["sooner"], events["later"]]

    assert unsave(client, events["later"]).status_code == 204
    assert saved_ids(client) == [events["sooner"]]


def test_saving_twice_keeps_one_row(client, monkeypatch, events):
    sign_in(client, monkeypatch)
    assert save(client, events["sooner"]).status_code == 201

    again = save(client, events["sooner"])
    assert again.status_code == 200 and again.get_json()["created"] is False
    assert SavedEvent.query.count() == 1


def test_unsaving_something_not_saved_is_fine(client, monkeypatch, events):
    sign_in(client, monkeypatch)
    assert unsave(client, events["sooner"]).status_code == 204
    assert unsave(client, 999999).status_code == 204


@pytest.mark.parametrize("body", [None, {}, {"event_id": "1"}, {"event_id": True}, {"event_id": 0},
                                  {"event_id": -5}, {"event_id": 1.5}, [1]])
def test_bad_requests_are_rejected(client, monkeypatch, events, body):
    sign_in(client, monkeypatch)
    response = client.post("/api/saved-events", json=body, headers=csrf_headers(client))
    assert response.status_code == 400
    assert SavedEvent.query.count() == 0


def test_unknown_event_is_404(client, monkeypatch, events):
    sign_in(client, monkeypatch)
    assert save(client, 999999).status_code == 404


def test_users_only_see_and_change_their_own_saves(app, monkeypatch, events):
    alice, bob = app.test_client(), app.test_client()
    sign_in(alice, monkeypatch, sub="google-sub-alice", email="alice@gmail.com")
    sign_in(bob, monkeypatch, sub="google-sub-bob", email="bob@gmail.com")

    assert save(alice, events["sooner"]).status_code == 201
    assert saved_ids(bob) == []

    # Bob can't remove Alice's save by guessing the event id.
    assert unsave(bob, events["sooner"]).status_code == 204
    assert saved_ids(alice) == [events["sooner"]]

    # Both can save the same event.
    assert save(bob, events["sooner"]).status_code == 201
    assert SavedEvent.query.count() == 2


def test_archiving_an_event_removes_its_saves(client, monkeypatch, events):
    sign_in(client, monkeypatch)
    save(client, events["sooner"])
    save(client, events["later"])

    # Run the archive just after "sooner" ends (no end time: it lasts until midnight).
    after_sooner = (SOON + timedelta(days=1, hours=6)).replace(tzinfo=timezone.utc)
    assert archive_past_events(after_sooner) == 1

    assert saved_ids(client) == [events["later"]]
    assert SavedEvent.query.count() == 1
