from tests.helpers import fake_google


def test_frontend_and_api_share_origin(client, app, tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>onCamp</html>", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('onCamp')", encoding="utf-8")
    app.config["FRONTEND_DIST_DIR"] = str(tmp_path)

    assert b"onCamp" in client.get("/").data
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/api/not-a-route").status_code == 404

    fake_google(monkeypatch)
    token = client.get("/api/auth/csrf").get_json()["csrf_token"]
    response = client.post(
        "/api/auth/google",
        json={"credential": "fake-google-token"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    assert client.get("/api/auth/me").get_json()["user"] is not None
