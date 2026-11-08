import os
from datetime import timedelta

from flask import current_app, jsonify, request

from app.api import api_bp
from app.api.auth_helpers import current_user, login_required
from app.services import DiscoveryService
from app.services.calendar_events import RANGES, get_calendar_events
from app.services.event_archive import campus_now


@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "service": "onCamp",
        "college": "Hunter",
        "environment": os.getenv("APP_ENV", "development"),
    })


@api_bp.route("/status", methods=["GET"])
def get_status():
    service = DiscoveryService()
    return jsonify({
        "college": "Hunter",
        "seed_account": service.seed_account,
        "pipeline": service.get_seed_context(),
    })


def _events_response(events, range_key):
    # All the events routes go through here so the sign-in limit is in one spot.
    # Logged out people only get the next ANON_EVENT_DAYS days. We send a count of
    # what was hidden so the page can ask them to sign in, but not the events themselves.
    locked = 0
    if current_user() is None:
        days = current_app.config.get("ANON_EVENT_DAYS", 7)
        cutoff = (campus_now().date() + timedelta(days=days)).isoformat()
        visible = [event for event in events if event["date"] <= cutoff]
        locked = len(events) - len(visible)
        events = visible

    response = jsonify({
        "range": range_key,
        "count": len(events),
        "events": events,
        "limited": locked > 0,
        "locked_count": locked,
    })
    # same URL gives different results depending on who is logged in
    response.headers["Vary"] = "Cookie"
    response.headers["Cache-Control"] = "private"
    return response


@api_bp.route("/events", methods=["GET"])
def get_all_upcoming_events():
    return _events_response(get_calendar_events(), "all")


def _club_id():
    value = request.args.get("club_id")
    if value is None or value == "":
        return None
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        raise ValueError("club_id must be a valid positive integer")
    if not 1 <= int(value) <= 2147483647:
        raise ValueError("club_id must be a valid positive integer")
    return int(value)


@api_bp.route("/events/filter", methods=["GET"])
def filter_events():
    range_key = request.args.get("range", "2w")
    if range_key not in RANGES:
        return jsonify({"error": f"range must be one of {list(RANGES)}"}), 400

    try:
        club_id = _club_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    events = get_calendar_events(range_key, club_id)
    return _events_response(events, range_key)


@api_bp.route("/events/archive", methods=["GET"])
@login_required
def get_archived_events():
    try:
        club_id = _club_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    events = get_calendar_events("all", club_id, include_past=True)
    return _events_response(events, "archive")
