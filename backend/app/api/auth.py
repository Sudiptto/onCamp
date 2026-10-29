import secrets
from datetime import datetime, timezone

from flask import current_app, jsonify, request, session
from flask_limiter.util import get_remote_address
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.exc import IntegrityError

from app.api import api_bp
from app.api.auth_helpers import current_user
from app.extensions import db, limiter
from app.models import User

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def _issue_csrf_token():
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def _valid_csrf_token():
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def _csrf_error():
    return jsonify({"error": "Your session expired. Refresh the page and try again."}), 403


@api_bp.get("/auth/csrf")
def get_csrf_token():
    token = session.get("csrf_token") or _issue_csrf_token()
    return jsonify({"csrf_token": token})


@api_bp.get("/auth/me")
def get_current_user():
    user = current_user()
    if user is None:
        session.pop("user_id", None)
        return jsonify({"user": None})
    return jsonify({"user": user.to_dict()})


@api_bp.post("/auth/google")
@limiter.limit("30 per 15 minutes", key_func=get_remote_address)
def google_login():
    # The browser gets a token from Google and sends it here.
    # We never trust it until the checks below pass.
    if not _valid_csrf_token():
        return _csrf_error()

    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not client_id:
        return jsonify({"error": "Google sign-in is not configured."}), 503

    body = request.get_json(silent=True)
    credential = body.get("credential") if isinstance(body, dict) else None
    if not isinstance(credential, str) or not credential or len(credential) > 4096:
        return jsonify({"error": "Send a valid Google credential."}), 400

    try:
        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,  # makes sure the token was made for our app
            clock_skew_in_seconds=10,
        )
    except google_exceptions.TransportError:
        return jsonify({"error": "Could not reach Google. Try again."}), 503
    except (ValueError, google_exceptions.GoogleAuthError):
        return jsonify({"error": "Google sign-in failed. Try again."}), 401

    sub = claims.get("sub")
    email = claims.get("email")
    if (
        claims.get("iss") not in GOOGLE_ISSUERS
        or not isinstance(sub, str)
        or not sub
        or not isinstance(email, str)
        or not email
        or claims.get("email_verified") not in (True, "true")
    ):
        return jsonify({"error": "Your Google account email must be verified."}), 401

    email = email.strip().lower()[:254]
    name = (claims.get("name") or "").strip()[:255] or None

    created = False
    user = User.query.filter_by(google_sub=sub).first()
    if user is None:
        user = User(google_sub=sub, email=email, name=name)
        db.session.add(user)
        created = True
    else:
        user.email = email
        user.name = name
    user.last_login_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
    except IntegrityError:
        # double click on first login, the other request already made the user
        db.session.rollback()
        user = User.query.filter_by(google_sub=sub).first()
        if user is None:
            raise
        created = False

    # start a brand new session on every login
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    token = _issue_csrf_token()
    return jsonify({"user": user.to_dict(), "csrf_token": token, "created": created})


@api_bp.post("/auth/logout")
def logout():
    if not _valid_csrf_token():
        return _csrf_error()
    session.clear()
    token = _issue_csrf_token()
    return jsonify({"user": None, "csrf_token": token})
