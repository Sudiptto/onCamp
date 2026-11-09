"""Turns a club's recent Instagram posts into upcoming events.

How the schedule fits together (this is the hard part of the cron job):

1. activity_check decides which clubs are "active" (posted in the last 90 days).
2. Active clubs get their posts scanned every ACTIVE_CHECK_INTERVAL_DAYS (2) days.
   find_clubs_due_for_post_scan() picks them using ClubPostCheckpoint.checked_at.
3. Posts are NOT stored. Every post is sent to the AI at most once, and only the ones
   that announce a future event become rows in `events`. To avoid re-scanning the same
   post, each club has a checkpoint holding the newest post id and date we processed;
   select_new_posts() drops anything at or before it.
4. Events whose date has already passed when the job runs are never added, and
   archive_past_events() moves finished events to `archived_events`.
5. A reminder post for an event we already have (same club, title and day) is skipped,
   matching the uq_events_club_title_day rule on the events table.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from app.extensions import db
from app.models import ArchivedEvent, Club, ClubActivity, ClubPostCheckpoint, College, Event
from app.services.event_archive import campus_now, event_has_passed
from jobs.activity_check.buckets import ACTIVE_CHECK_INTERVAL_DAYS
from jobs.post_extraction.ai import ExtractionError, extract_with_deepseek, find_google_form_url
from jobs.post_extraction.posts import extract_recent_posts


def _naive_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def find_clubs_due_for_post_scan(
    college_key: str, now: datetime | None = None, limit: int | None = None
) -> list[Club]:
    """Active clubs whose posts have never been scanned, or were last scanned 2+ days ago."""
    now = _naive_utc(now or datetime.now(timezone.utc))
    college = College.query.filter_by(key=college_key).first()
    if college is None:
        raise ValueError(f"No College row for key={college_key!r}.")

    query = (
        Club.query
        .join(ClubActivity, ClubActivity.club_id == Club.id)
        .outerjoin(ClubPostCheckpoint, ClubPostCheckpoint.club_id == Club.id)
        .filter(Club.college_id == college.id)
        .filter(ClubActivity.status == "active")
        .filter(Club.instagram_user_id.isnot(None))
        .filter(
            ClubPostCheckpoint.id.is_(None)
            | (ClubPostCheckpoint.checked_at <= now - timedelta(days=ACTIVE_CHECK_INTERVAL_DAYS))
        )
        .order_by(Club.id)
    )
    return query.limit(limit).all() if limit else query.all()


def select_new_posts(
    posts: list[dict[str, Any]],
    checkpoint_at: datetime | None,
    seen_ids: set[str],
) -> list[dict[str, Any]]:
    """Return only posts we have not processed yet, oldest first.

    A post is skipped if it already produced an event, or if it is not newer than the
    checkpoint (the newest post processed on a previous run).
    """
    new_posts = []
    for post in posts:
        if post["post_id"] in seen_ids:
            continue
        if checkpoint_at is not None and _naive_utc(post["taken_at"]) <= checkpoint_at:
            continue
        new_posts.append(post)
    return sorted(new_posts, key=lambda post: post["taken_at"])


def _save_checkpoint(
    checkpoint: ClubPostCheckpoint | None,
    club_id: int,
    checked_at: datetime,
    post_id: str | None = None,
    post_at: datetime | None = None,
) -> ClubPostCheckpoint:
    if checkpoint is None:
        checkpoint = ClubPostCheckpoint(club_id=club_id)
        db.session.add(checkpoint)
    if post_id is not None:
        checkpoint.last_post_id = post_id
        checkpoint.last_post_at = post_at
    checkpoint.checked_at = checked_at
    return checkpoint


def process_club_posts(
    club: Club,
    raw_medias: Any,
    count: int,
    extractor: Any = extract_with_deepseek,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run AI extraction on a club's newest `count` unchecked posts and save upcoming events.

    Posts are handled oldest first and the checkpoint moves forward after each one, so if
    the AI fails mid-run the failed post (and anything newer) is retried next time.
    `now` is the moment the cron job launched; events before it are not added.
    """
    now = _naive_utc(now or datetime.now(timezone.utc))
    local_now = campus_now(now)
    college = db.session.get(College, club.college_id)
    recent = extract_recent_posts(raw_medias, count)
    recent_ids = [post["post_id"] for post in recent]

    checkpoint = ClubPostCheckpoint.query.filter_by(club_id=club.id).first()
    seen_ids = {
        post_id
        for model in (Event, ArchivedEvent)
        for (post_id,) in db.session.query(model.post_id).filter(model.post_id.in_(recent_ids))
    }
    new_posts = select_new_posts(recent, checkpoint.last_post_at if checkpoint else None, seen_ids)

    events: list[Event] = []
    not_events = past_events = undated_events = duplicate_events = 0
    error = None
    for post in new_posts:
        posted_at = _naive_utc(post["taken_at"])
        try:
            details = extractor(post["caption"], posted_at, club.name, college.name)
        except ExtractionError as exc:
            error = f"{post['post_id']}: {exc}"
            break

        if not (details["is_event"] and details["title"]):
            not_events += 1
        elif details["start_time"] is None:
            undated_events += 1  # without a date we can't tell if it's upcoming
        elif event_has_passed(details["start_time"], details["end_time"], local_now):
            past_events += 1
        elif Event.find_duplicate(club.id, details["title"], details["start_time"]):
            # A reminder or repost of an event we already have (same club, title and day).
            # The events table also refuses these, so skip it here instead of failing the run.
            duplicate_events += 1
        else:
            event = Event(
                club_id=club.id,
                college_id=club.college_id,
                post_id=post["post_id"],
                title=details["title"],
                description=details["description"],
                start_time=details["start_time"],
                end_time=details["end_time"],
                location=details["location"],
                is_free_food=details["has_free_food"],
                google_form_url=find_google_form_url(post["caption"]),
                source_url=post["post_url"],
            )
            db.session.add(event)
            events.append(event)

        checkpoint = _save_checkpoint(checkpoint, club.id, now, post["post_id"], posted_at)
        db.session.commit()

    if error is None:
        # Record the scan even when nothing was new so the club isn't "due" again right away.
        _save_checkpoint(checkpoint, club.id, now)
        db.session.commit()

    return {
        "fetched": len(recent),
        "already_checked": len(recent) - len(new_posts),
        "processed": len(events) + not_events + past_events + undated_events + duplicate_events,
        "events": events,
        "not_events": not_events,
        "past_events": past_events,
        "undated_events": undated_events,
        "duplicate_events": duplicate_events,
        "error": error,
    }
