"""Keeps the events table limited to upcoming events.

Event times are stored in campus local time (America/New_York) without a timezone,
so "now" has to be converted to that same clock before comparing.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import ArchivedEvent, Event

CAMPUS_TZ = ZoneInfo("America/New_York")


def campus_now(now: datetime | None = None) -> datetime:
    """Current time on the campus clock, as a naive datetime."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(CAMPUS_TZ).replace(tzinfo=None)


def event_has_passed(start_time: datetime, end_time: datetime | None, local_now: datetime) -> bool:
    """True once an event is over. With no end time, it lasts until the end of its start day,
    so a date-only event (midnight start) is not archived the morning it happens."""
    if end_time is None:
        end_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return end_time <= local_now


def archive_past_events(now: datetime | None = None) -> int:
    """Move every finished event from `events` to `archived_events`. Returns how many moved.

    Run this at the start of each scan so the events table only ever holds upcoming events.
    """
    local_now = campus_now(now)
    archived_at = (now or datetime.now(timezone.utc))
    if archived_at.tzinfo is not None:
        archived_at = archived_at.astimezone(timezone.utc).replace(tzinfo=None)

    moved = 0
    for event in Event.query.all():
        # An event with no start time can't be dated, so it can't be judged to be over.
        if event.start_time is None or not event_has_passed(event.start_time, event.end_time, local_now):
            continue
        db.session.add(ArchivedEvent(
            club_id=event.club_id,
            college_id=event.college_id,
            post_id=event.post_id,
            title=event.title,
            description=event.description,
            start_time=event.start_time,
            end_time=event.end_time,
            location=event.location,
            is_free_food=event.is_free_food,
            google_form_url=event.google_form_url,
            source_url=event.source_url,
            created_at=event.created_at,
            archived_at=archived_at,
        ))
        db.session.delete(event)
        moved += 1
    db.session.commit()
    return moved
