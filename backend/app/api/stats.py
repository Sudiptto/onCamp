import os
import time

from flask import current_app, jsonify
from sqlalchemy import func

from app.api import api_bp
from app.extensions import db
from app.models import Club, Event, User
from app.services.event_archive import campus_now

# How long to reuse the numbers so page views don't hit the database every time.
CACHE_SECONDS = 600
_cache = {"at": 0.0, "data": None}

# What we send if the database fails and there is nothing cached yet.
EMPTY = {"users_milestone": None, "clubs": 0, "upcoming_events": 0}


def user_milestone(count):
    # Keep the first two digits and zero the rest, so the number is never more than
    # about 9% below the real one (249 -> 240, 1,234 -> 1,200, 12,300 -> 12,000).
    # Under 100 we return None so the page shows nothing instead of a small number.
    if count < 100:
        return None
    step = 10 ** (len(str(count)) - 2)
    return (count // step) * step


def _excluded_emails():
    # Team and test accounts we don't want in the public number.
    raw = current_app.config.get("STATS_EXCLUDED_EMAILS")
    if raw is None:
        raw = os.getenv("STATS_EXCLUDED_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _unique_people():
    # One per email address (ignoring case), so a recreated account or a repeated
    # row can't count twice. Rows that never finished a sign-in don't count.
    query = db.session.query(func.count(func.distinct(func.lower(User.email)))).filter(
        User.last_login_at.isnot(None)
    )
    excluded = _excluded_emails()
    if excluded:
        query = query.filter(~func.lower(User.email).in_(excluded))
    return query.scalar() or 0


def _build_stats():
    # Event times are saved on the campus clock (New York) with no timezone, so compare
    # against campus time, not the server's. Finished events can sit in the table until the
    # next scan archives them, so filter them out here. Duplicate events can't exist: the
    # database refuses a second event for the same club, title and day.
    upcoming = db.session.query(Event).filter(Event.start_time >= campus_now()).count()
    return {
        # Only a rounded milestone. Never the real count, never any user info.
        "users_milestone": user_milestone(_unique_people()),
        "clubs": db.session.query(Club).filter(Club.is_active.is_(True)).count(),
        "upcoming_events": upcoming,
    }


@api_bp.get("/stats")
def get_stats():
    # No query parameters are read, so nobody can change the result with the URL.
    now = time.monotonic()
    if _cache["data"] is None or now - _cache["at"] > CACHE_SECONDS:
        try:
            _cache["data"] = _build_stats()
            _cache["at"] = now
        except Exception:
            db.session.rollback()
            current_app.logger.exception("stats query failed")
            # Keep showing the last good numbers, or nothing if we have none.
            data = _cache["data"] or EMPTY
            response = jsonify(data)
            response.headers["Cache-Control"] = "no-store"
            return response
    response = jsonify(_cache["data"])
    response.headers["Cache-Control"] = "public, max-age=300"
    return response
