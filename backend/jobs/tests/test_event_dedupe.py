from datetime import datetime, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import Club, Event, SavedEvent, User
from app.services.event_dedupe import titles_match
from dedupe_events import ensure_unique_index, find_duplicate_groups, merge_group
from jobs.post_extraction import ai
from jobs.post_extraction.ai import ExtractionError, judge_same_event_with_deepseek
from jobs.post_extraction.club_posts import process_club_posts
from seed_colleges import seed_colleges
from sync_clubs import sync_clubs

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
SHOW_NIGHT = datetime(2026, 11, 20, 16, 30)


@pytest.fixture
def club():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite://", "TESTING": True, "RATELIMIT_ENABLED": False, "AUTO_CREATE_TABLES": True})
    with app.app_context():
        seed_colleges()
        sync_clubs([{"username": "hunter_sacc", "user_id": "1", "full_name": "South Asian Culture Club"}], "hunter")
        yield Club.query.first()


def add_event(club, post_id, title, start=SHOW_NIGHT, **fields):
    event = Event(
        club_id=club.id, college_id=club.college_id, post_id=post_id, title=title, start_time=start, **fields
    )
    db.session.add(event)
    db.session.commit()
    return event


@pytest.mark.parametrize("first, second", [
    ("Mehndi Ki Raat", "Mehendi Ki Raat"),
    ("Mehndi Ki Raat", "mehndi ki raat!"),
    ("General Body Meeting", "General Body Meeting (GBM)"),
])
def test_titles_that_name_the_same_event_match(first, second):
    assert titles_match(first, second)


@pytest.mark.parametrize("first, second", [
    ("Mock Mehendi", "Mehndi Ki Raat"),
    ("Meeting", "General Body Meeting"),
    ("Python Basics Night", "Python Advanced Night"),
    ("Movie Night: Short Films", "Movie Night: Horror"),
    ("Intro to Git Part 1", "Intro to Git Part 2"),
    ("future event", "future event two"),
    ("Intro to Git", "Intro to Git Workshop"),  # reworded, so this one is the AI's job
    ("", "Mehndi Ki Raat"),
])
def test_different_events_do_not_match(first, second):
    assert not titles_match(first, second)


def test_reminder_with_a_reworded_title_adds_its_room_to_the_original(club):
    raw = {"items": [
        {"pk": "1", "code": "C1", "taken_at": 1000, "caption": {"text": "announcement"}},
        {"pk": "2", "code": "C2", "taken_at": 2000, "caption": {"text": "reminder"}},
    ]}

    def extractor(caption, posted_at, club_name, college_name):
        reminder = caption == "reminder"
        return {
            "is_event": True,
            "title": "Mehendi Ki Raat" if reminder else "Mehndi Ki Raat",
            "description": None,
            "start_time": SHOW_NIGHT,
            "end_time": datetime(2026, 11, 20, 20, 30),
            "location": "Faculty Dining Room, West 8th Floor" if reminder else None,
            "has_free_food": False,
        }

    result = process_club_posts(club, raw, 5, extractor=extractor, now=NOW)

    event = Event.query.one()
    assert result["duplicate_events"] == 1
    assert event.post_id == "1" and event.title == "Mehndi Ki Raat"
    assert event.location == "Faculty Dining Room, West 8th Floor"


def test_reminder_does_not_overwrite_what_the_original_already_has(club):
    add_event(club, "1", "Mehndi Ki Raat", location="Hunter West 420")
    duplicate = Event.find_duplicate(club.id, "Mehendi Ki Raat", SHOW_NIGHT.replace(hour=0, minute=0))
    assert duplicate is not None and duplicate.location == "Hunter West 420"


def test_cleanup_merges_existing_duplicates_and_moves_saves(club):
    keeper = add_event(club, "1", "Mehndi Ki Raat")
    copy = add_event(club, "2", "Mehendi Ki Raat", location="Faculty Dining Room, West 8th Floor")
    other_day = add_event(club, "3", "Mehndi Ki Raat", start=datetime(2026, 11, 27, 16, 30))
    mock = add_event(club, "4", "Mock Mehendi", start=SHOW_NIGHT.replace(hour=0, minute=0))

    users = [User(email=f"u{i}@example.com", google_sub=f"g{i}") for i in range(2)]
    db.session.add_all(users)
    db.session.commit()
    db.session.add_all([
        SavedEvent(user_id=users[0].id, event_id=copy.id),  # saved only the copy
        SavedEvent(user_id=users[1].id, event_id=keeper.id),
        SavedEvent(user_id=users[1].id, event_id=copy.id),  # saved both
    ])
    db.session.commit()

    groups = find_duplicate_groups(Event.query.all())
    assert [[event.id for event in group] for group in groups] == [[keeper.id, copy.id]]

    assert merge_group(groups[0]) == 1
    db.session.commit()

    assert {event.id for event in Event.query} == {keeper.id, other_day.id, mock.id}
    assert db.session.get(Event, keeper.id).location == "Faculty Dining Room, West 8th Floor"
    assert {(s.user_id, s.event_id) for s in SavedEvent.query} == {
        (users[0].id, keeper.id), (users[1].id, keeper.id),
    }


def test_ensure_unique_index_adds_a_missing_index_once(club):
    # an old database file from before the index existed
    db.session.execute(db.text("DROP INDEX uq_events_club_title_day"))
    db.session.commit()

    assert ensure_unique_index() is True
    assert ensure_unique_index() is False


# AI check

def henna_night_extractor(caption, posted_at, club_name, college_name):
    # same night, but the reminder uses a different name and adds the room
    reminder = caption == "reminder"
    return {
        "is_event": True,
        "title": "Henna Night" if reminder else "Mehndi Ki Raat",
        "description": None,
        "start_time": SHOW_NIGHT,
        "end_time": None,
        "location": "Faculty Dining Room" if reminder else None,
        "has_free_food": False,
    }


TWO_POSTS = {"items": [
    {"pk": "1", "code": "C1", "taken_at": 1000, "caption": {"text": "announcement"}},
    {"pk": "2", "code": "C2", "taken_at": 2000, "caption": {"text": "reminder"}},
]}


def test_ai_says_a_differently_named_post_is_the_same_event(club):
    asked = []

    def judge(new_post, candidates):
        asked.append((new_post["title"], [event.title for event in candidates]))
        return candidates[0].id

    result = process_club_posts(
        club, TWO_POSTS, 5, extractor=henna_night_extractor, now=NOW, duplicate_judge=judge
    )

    assert asked == [("Henna Night", ["Mehndi Ki Raat"])]
    event = Event.query.one()
    assert event.title == "Mehndi Ki Raat" and event.location == "Faculty Dining Room"
    assert result["duplicate_events"] == 1
    assert result["ai_duplicate_checks"] == 1 and result["ai_duplicates_found"] == 1


def test_ai_says_it_is_a_different_event(club):
    result = process_club_posts(
        club, TWO_POSTS, 5, extractor=henna_night_extractor, now=NOW,
        duplicate_judge=lambda new_post, candidates: None,
    )

    assert Event.query.count() == 2
    assert result["ai_duplicate_checks"] == 1 and result["ai_duplicates_found"] == 0


def test_ai_failure_keeps_the_event_and_does_not_stop_the_scan(club):
    def broken(new_post, candidates):
        raise ExtractionError("DeepSeek request failed: timeout")

    result = process_club_posts(
        club, TWO_POSTS, 5, extractor=henna_night_extractor, now=NOW, duplicate_judge=broken
    )

    assert Event.query.count() == 2
    assert result["error"] is None and result["processed"] == 2


def test_ai_is_not_asked_when_the_free_check_already_found_the_duplicate(club):
    def never(new_post, candidates):
        raise AssertionError("should not be called")

    def same_title(caption, posted_at, club_name, college_name):
        return {**henna_night_extractor(caption, posted_at, club_name, college_name), "title": "Mehndi Ki Raat"}

    result = process_club_posts(club, TWO_POSTS, 5, extractor=same_title, now=NOW, duplicate_judge=never)

    assert Event.query.count() == 1 and result["ai_duplicate_checks"] == 0


def test_ai_is_not_asked_when_the_club_has_nothing_else_that_day(club):
    def never(new_post, candidates):
        raise AssertionError("should not be called")

    raw = {"items": [{"pk": "1", "code": "C1", "taken_at": 1000, "caption": {"text": "announcement"}}]}
    result = process_club_posts(club, raw, 5, extractor=henna_night_extractor, now=NOW, duplicate_judge=never)

    assert Event.query.count() == 1 and result["ai_duplicate_checks"] == 0


@pytest.mark.parametrize("answer, expected", [
    ('{"duplicate_of": 7, "reason": "same night"}', 7),
    ('{"duplicate_of": null, "reason": "different"}', None),
    ('{"duplicate_of": 999, "reason": "made up id"}', None),
    ('{"duplicate_of": true, "reason": "bool is not an id"}', None),
])
def test_judge_only_accepts_ids_it_was_given(monkeypatch, answer, expected):
    class Existing:
        id, title, description, location = 7, "Mehndi Ki Raat", None, None
        start_time, end_time = SHOW_NIGHT, None

    monkeypatch.setattr(ai, "_ask_deepseek", lambda prompt_path, payload: answer)
    new_post = {"title": "Henna Night", "start_time": SHOW_NIGHT, "caption": "reminder"}

    assert judge_same_event_with_deepseek(new_post, [Existing()]) == expected


def test_judge_rejects_an_answer_that_is_not_json(monkeypatch):
    monkeypatch.setattr(ai, "_ask_deepseek", lambda prompt_path, payload: "sure, same event!")
    with pytest.raises(ExtractionError):
        judge_same_event_with_deepseek({"title": "x", "start_time": SHOW_NIGHT}, [])
