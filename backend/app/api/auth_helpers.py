import secrets
from functools import wraps

from flask import jsonify, request, session

from app.extensions import db
from app.models import User


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def login_required(view):
    # Put this on any route that needs a login. Hiding stuff in React is not enough.
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return jsonify({"error": "Sign in to continue.", "code": "login_required"}), 401
        return view(*args, **kwargs)

    return wrapped


def issue_csrf_token():
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def valid_csrf_token():
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def csrf_error():
    return jsonify({"error": "Your session expired. Refresh the page and try again."}), 403


def csrf_required(view):
    # Put this on any route that changes data. The browser sends the cookie on its own,
    # so the X-CSRF-Token header is what proves the request came from our page.
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not valid_csrf_token():
            return csrf_error()
        return view(*args, **kwargs)

    return wrapped
