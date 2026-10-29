from functools import wraps

from flask import jsonify, session

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
