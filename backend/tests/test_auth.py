from google.auth.exceptions import TransportError

from app.models import User
from tests.helpers import csrf_headers, fake_google, google_login, sign_in


def test_google_login_creates_account_and_normalizes_email(client, app, monkeypatch):
    calls = fake_google(monkeypatch)
    response = google_login(client)

    assert response.status_code == 200
    body = response.get_json()
    assert body["created"] is True
    assert body["user"]["email"] == "student@gmail.com"
    assert body["user"]["name"] == "Sam Student"
    assert "google_sub" not in body["user"]
    assert body["csrf_token"]
    # should be checked against our own client id
    assert calls == [("fake-google-token", "test-client-id.apps.googleusercontent.com")]

    with app.app_context():
        assert User.query.count() == 1


def test_second_login_reuses_account_and_refreshes_email(client, app, monkeypatch):
    sign_in(client, monkeypatch)
    fake_google(monkeypatch, email="new.address@gmail.com")
    response = google_login(client)

    assert response.get_json()["created"] is False
    assert response.get_json()["user"]["email"] == "new.address@gmail.com"
    with app.app_context():
        assert User.query.count() == 1


def test_different_google_accounts_are_different_users(client, app, monkeypatch):
    sign_in(client, monkeypatch, sub="sub-a")
    sign_in(client, monkeypatch, sub="sub-b", email="other@gmail.com")
    with app.app_context():
        assert User.query.count() == 2


def test_login_requires_csrf_header(client, monkeypatch):
    fake_google(monkeypatch)
    response = client.post("/api/auth/google", json={"credential": "fake-google-token"})
    assert response.status_code == 403
    assert client.get("/api/auth/me").get_json()["user"] is None


def test_invalid_google_token_is_rejected(client, monkeypatch):
    fake_google(monkeypatch, error=ValueError("bad token"))
    assert google_login(client).status_code == 401
    assert client.get("/api/auth/me").get_json()["user"] is None


def test_unverified_google_email_is_rejected(client, app, monkeypatch):
    fake_google(monkeypatch, email_verified=False)
    assert google_login(client).status_code == 401
    with app.app_context():
        assert User.query.count() == 0


def test_wrong_issuer_is_rejected(client, monkeypatch):
    fake_google(monkeypatch, iss="https://evil.example.com")
    assert google_login(client).status_code == 401


def test_google_unreachable_returns_503(client, monkeypatch):
    fake_google(monkeypatch, error=TransportError("offline"))
    assert google_login(client).status_code == 503


def test_missing_or_malformed_credential_returns_400(client, monkeypatch):
    fake_google(monkeypatch)
    headers = csrf_headers(client)
    assert client.post("/api/auth/google", json={}, headers=headers).status_code == 400
    assert client.post("/api/auth/google", json={"credential": 123}, headers=headers).status_code == 400
    assert client.post("/api/auth/google", data="not-json", headers=headers).status_code == 400


def test_login_fails_cleanly_when_google_is_not_configured(client, app, monkeypatch):
    fake_google(monkeypatch)
    app.config["GOOGLE_CLIENT_ID"] = ""
    assert google_login(client).status_code == 503


def test_session_persists_then_logout_clears_it(client, monkeypatch):
    sign_in(client, monkeypatch)
    assert client.get("/api/auth/me").get_json()["user"]["email"] == "student@gmail.com"

    response = client.post("/api/auth/logout", json={}, headers=csrf_headers(client))
    assert response.status_code == 200
    assert client.get("/api/auth/me").get_json()["user"] is None


def test_logout_requires_csrf_header(client, monkeypatch):
    sign_in(client, monkeypatch)
    assert client.post("/api/auth/logout", json={}).status_code == 403
    assert client.get("/api/auth/me").get_json()["user"] is not None


def test_current_user_does_not_expose_google_id(client, monkeypatch):
    sign_in(client, monkeypatch)
    user = client.get("/api/auth/me").get_json()["user"]
    assert "google_sub" not in user
