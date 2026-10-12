import json

import pytest
import requests

from app.services import hiker_client
from app.services.hiker_client import HikerAPIError, HikerClient
from jobs.activity_check.pipeline import run


class FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = json.dumps(self._body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self._body


@pytest.fixture
def client():
    return HikerClient(base_url="https://example.test", access_key="test-key")


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(hiker_client.time, "sleep", recorded.append)
    return recorded


def fake_get(monkeypatch, responses):
    calls = []

    def _get(url, **kwargs):
        calls.append(url)
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(hiker_client.requests, "get", _get)
    return calls


def test_get_retries_rate_limit(client, sleeps, monkeypatch):
    calls = fake_get(monkeypatch, [FakeResponse(429), FakeResponse(200, {"ok": True})])

    assert client.get("/x") == {"ok": True}
    assert len(calls) == 2
    assert sleeps == [1.0]


def test_get_respects_retry_after_cap(client, sleeps, monkeypatch):
    fake_get(monkeypatch, [
        FakeResponse(429, headers={"Retry-After": "5"}),
        FakeResponse(429, headers={"Retry-After": "9999"}),
        FakeResponse(200, {"ok": True}),
    ])

    client.get("/x")
    assert sleeps == [5.0, hiker_client.MAX_RETRY_DELAY_SECONDS]


def test_get_raises_after_max_retries(client, sleeps, monkeypatch):
    calls = fake_get(monkeypatch, [FakeResponse(429)] * (hiker_client.MAX_RETRIES + 1))

    with pytest.raises(HikerAPIError) as caught:
        client.get("/x")

    assert caught.value.status_code == 429
    assert len(calls) == hiker_client.MAX_RETRIES + 1


def test_get_does_not_retry_404(client, sleeps, monkeypatch):
    calls = fake_get(monkeypatch, [FakeResponse(404), FakeResponse(200)])

    with pytest.raises(HikerAPIError) as caught:
        client.get("/x")

    assert caught.value.status_code == 404
    assert len(calls) == 1
    assert sleeps == []


def test_get_network_error_has_no_status(client, sleeps, monkeypatch):
    fake_get(monkeypatch, [requests.Timeout("slow")])

    with pytest.raises(HikerAPIError) as caught:
        client.get("/x")

    assert caught.value.status_code is None


def test_get_error_hides_api_key(client, sleeps, monkeypatch):
    fake_get(monkeypatch, [FakeResponse(500, {"detail": "nope"})])

    with pytest.raises(HikerAPIError) as caught:
        client.get("/x")

    assert "test-key" not in str(caught.value)


def test_activity_pipeline_stops_on_rate_limit(tmp_path):
    clubs = [{"user_id": str(n), "username": f"club{n}"} for n in range(1, 5)]
    clubs_path = tmp_path / "clubs.json"
    clubs_path.write_text(json.dumps(clubs), encoding="utf-8")
    asked = []

    class AlwaysThrottled:
        def get_user_medias(self, user_id):
            asked.append(user_id)
            raise HikerAPIError("slow down", status_code=429)

    result = run(clubs_path, tmp_path / "out.json", client=AlwaysThrottled())

    assert asked == ["1"]
    assert result["errors"][0]["status_code"] == 429
