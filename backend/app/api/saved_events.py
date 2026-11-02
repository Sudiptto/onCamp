"""Saved events: a signed-in student's bookmarks, stored in the saved_events table.

Every route needs a login, and the two that change data also need the X-CSRF-Token header.
A user only ever sees or changes their own rows: the user id always comes from the session,
never from the request.
"""

from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from app.api import api_bp
from app.api.auth_helpers import csrf_required, current_user, login_required
from app.extensions import db
from app.models import Event, SavedEvent


def _private(response, status=200):
    # Each user gets different results from the same URL, so never cache it in a shared cache.
    response.headers["Cache-Control"] = "private, no-store"
    return response, status


@api_bp.get("/saved-events")
@login_required
def list_saved_events():
    rows = (
        SavedEvent.query.join(Event)
        .filter(SavedEvent.user_id == current_user().id)
        .order_by(Event.start_time, Event.id)
        .all()
    )
    return _private(jsonify({"count": len(rows), "saved_events": [row.to_dict() for row in rows]}))


@api_bp.post("/saved-events")
@login_required
@csrf_required
def save_event():
    body = request.get_json(silent=True)
    event_id = body.get("event_id") if isinstance(body, dict) else None
    # bool is a subclass of int in Python, so `true` would otherwise pass as event 1.
    if not isinstance(event_id, int) or isinstance(event_id, bool) or event_id < 1:
        return jsonify({"error": "Send the id of the event to save."}), 400

    if db.session.get(Event, event_id) is None:
        return jsonify({"error": "That event doesn't exist or has already happened."}), 404

    user = current_user()
    existing = SavedEvent.query.filter_by(user_id=user.id, event_id=event_id).first()
    if existing is not None:
        return _private(jsonify({"saved": existing.to_dict(), "created": False}))

    saved = SavedEvent(user_id=user.id, event_id=event_id)
    db.session.add(saved)
    try:
        db.session.commit()
    except IntegrityError:
        # Double click or two tabs: the other request saved it first. The unique rule on
        # (user_id, event_id) stopped the copy, so the result is the same either way.
        db.session.rollback()
        saved = SavedEvent.query.filter_by(user_id=user.id, event_id=event_id).first()
        if saved is None:
            # Not a duplicate: the event was archived between our check and the insert.
            return jsonify({"error": "That event doesn't exist or has already happened."}), 404
        return _private(jsonify({"saved": saved.to_dict(), "created": False}))

    return _private(jsonify({"saved": saved.to_dict(), "created": True}), 201)


@api_bp.delete("/saved-events/<int:event_id>")
@login_required
@csrf_required
def unsave_event(event_id):
    # Filtering on the session's user id is what stops one user from removing another's save.
    SavedEvent.query.filter_by(user_id=current_user().id, event_id=event_id).delete()
    db.session.commit()
    # Deleting something that isn't saved is not an error: the end state is what was asked for.
    return "", 204
