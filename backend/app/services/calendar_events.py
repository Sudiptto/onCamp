"""Database-backed calendar queries and response formatting."""

from datetime import datetime, time, timedelta

from sqlalchemy import and_, or_

from app.models import ArchivedEvent, Club, Event
from app.services.event_archive import campus_now

RANGES = {"1w": 7, "2w": 14, "1m": 30, "semester": 120, "all": None}
ARCHIVE_DAYS = 120


def _format_event(event, club):
    # Post IDs survive moving an event from the live table to the archive.
    event_id = f"post:{event.post_id}" if event.post_id else f"{event.__tablename__}:{event.id}"
    return {
        "event_id": event_id,
        "club_id": str(club.id),
        "club_name": club.name,
        "club_link": f"https://www.instagram.com/{club.instagram_handle}/",
        "club_pfp": club.profile_pic_url,
        "event_name": event.title,
        "event_link": event.google_form_url,
        "free_food": bool(event.is_free_food),
        "date": event.start_time.date().isoformat(),
        "start_time": event.start_time.strftime("%H:%M"),
        "end_time": event.end_time.strftime("%H:%M") if event.end_time else None,
        "start_datetime": event.start_time.isoformat(),
        "location": event.location,
        "post_link": event.source_url,
    }


def get_calendar_events(range_key="all", club_id=None, include_past=False, now=None):
    """Return dated events in campus time; include finished events only for the archive."""
    local_now = campus_now(now)
    today = local_now.date()
    start_of_today = datetime.combine(today, time.min)

    def query_events(model):
        query = model.query.join(Club, model.club_id == Club.id).filter(model.start_time.isnot(None))
        if club_id is not None:
            query = query.filter(model.club_id == club_id)
        if include_past:
            query = query.filter(model.start_time >= start_of_today - timedelta(days=ARCHIVE_DAYS))
        else:
            # Match archive_past_events: ongoing and date-only events stay visible.
            query = query.filter(or_(
                model.end_time > local_now,
                and_(model.end_time.is_(None), model.start_time >= start_of_today),
            ))
            days = RANGES[range_key]
            if days is not None:
                query = query.filter(model.start_time < start_of_today + timedelta(days=days + 1))
        return query.with_entities(model, Club).all()

    rows = query_events(Event)
    if include_past:
        rows += query_events(ArchivedEvent)
    rows.sort(key=lambda row: (row[0].start_time, row[0].id))
    return [_format_event(event, club) for event, club in rows]
