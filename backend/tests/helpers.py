from app.api import auth


def csrf_headers(client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.get_json()["csrf_token"]}


def fake_google(monkeypatch, error=None, **overrides):
    # Fake Google's token check so tests don't hit the internet.
    # Returns the list of calls so a test can look at what was passed in.
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "google-sub-1",
        "email": "Student@Gmail.com",
        "email_verified": True,
        "name": "Sam Student",
        **overrides,
    }
    calls = []

    def fake_verify(token, request, audience=None, clock_skew_in_seconds=0):
        calls.append((token, audience))
        if error is not None:
            raise error
        return claims

    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", fake_verify)
    return calls


def google_login(client, credential="fake-google-token"):
    return client.post(
        "/api/auth/google",
        json={"credential": credential},
        headers=csrf_headers(client),
    )


def sign_in(client, monkeypatch, **overrides):
    fake_google(monkeypatch, **overrides)
    response = google_login(client)
    assert response.status_code == 200
    return response
