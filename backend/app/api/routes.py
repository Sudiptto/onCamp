import os
from datetime import date, timedelta

from flask import current_app, jsonify, request

from app.api import api_bp
from app.api.auth_helpers import current_user, login_required
from app.api.mock_events import RANGES, get_mock_events
from app.services import DiscoveryService


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
    # TODO: when events come from the database, put this cutoff in the query too.
    locked = 0
    if current_user() is None:
        days = current_app.config.get("ANON_EVENT_DAYS", 7)
        cutoff = (date.today() + timedelta(days=days)).isoformat()
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
    # FILTER VIA DATABASE
    # Later: SELECT upcoming events (start >= now) from the DB, ordered by start.
    return _events_response(get_mock_events("all"), "all")


@api_bp.route("/events/filter", methods=["GET"])
def filter_events():
    # FILTER VIA DATABASE
    # Later: add start <= now + window and club_id to the upcoming-events query.
    range_key = request.args.get("range", "2w")
    if range_key not in RANGES:
        return jsonify({"error": f"range must be one of {list(RANGES)}"}), 400

    events = get_mock_events(range_key, request.args.get("club_id"))
    return _events_response(events, range_key)


@api_bp.route("/events/archive", methods=["GET"])
@login_required
def get_archived_events():
    # FILTER VIA DATABASE
    # Later: SELECT all events (past + upcoming) since the start of last semester.
    events = get_mock_events("all", request.args.get("club_id"), include_past=True)
    return _events_response(events, "archive")
