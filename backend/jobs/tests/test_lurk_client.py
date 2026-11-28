import json

import pytest
import requests

from app.services import lurk_client
from app.services.lurk_client import LurkAPIError, LurkClient


class FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None, text=""):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = text or json.dumps(self._body)

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.fixture
def client():
    return LurkClient(base_url="https://example.test", api_key="test-key")


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(lurk_client.time, "sleep", recorded.append)
    return recorded


def fake_get(monkeypatch, responses):
    calls = []

    def _get(url, **kwargs):
        calls.append({"url": url, "params": kwargs.get("params"), "headers": kwargs.get("headers")})
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(lurk_client.requests, "get", _get)
    return calls


def test_missing_key_does_not_call_the_network(monkeypatch):
    called = fake_get(monkeypatch, [])
    with pytest.raises(LurkAPIError, match="LURK_API_KEY"):
        LurkClient(base_url="https://example.test", api_key="").get_user_posts("hunter_bsa")
    assert called == []


def test_user_posts_uses_username_and_records_one_credit(client, monkeypatch):
    calls = fake_get(monkeypatch, [FakeResponse(200, {
        "success": True,
        "credits_charged": 1,
        "credits_remaining": 49999,
        "posts": [],
    })])

    data = client.get_user_posts("@hunter_bsa", first=99)

    assert data["credits_remaining"] == 49999
    assert calls[0]["url"] == "https://example.test/v2/instagram/user/posts"
    assert calls[0]["params"] == {"username": "hunter_bsa", "first": 50}
    assert calls[0]["headers"]["x-api-key"] == "test-key"
    assert client.credits_charged == 1
    assert client.credits_remaining == 49999


def test_retries_rate_limit_then_records_only_platform_charges(client, sleeps, monkeypatch):
    fake_get(monkeypatch, [
        FakeResponse(429, {"success": False, "code": "rate_limited", "error": "slow down", "credits_charged": 0}),
        FakeResponse(200, {"success": True, "credits_charged": 1, "credits_remaining": 10, "posts": []}),
    ])

    client.get_user_posts("hunter_bsa")

    assert sleeps == [1.0]
    assert client.credits_charged == 1


def test_not_found_is_charged_and_not_retried(client, sleeps, monkeypatch):
    fake_get(monkeypatch, [FakeResponse(404, {
        "success": False,
        "code": "not_found",
        "error": "missing",
        "credits_charged": 1,
        "credits_remaining": 42,
    })])

    with pytest.raises(LurkAPIError) as caught:
        client.get_user_posts("missing_club")

    assert caught.value.status_code == 404
    assert caught.value.code == "not_found"
    assert sleeps == []
    assert client.credits_charged == 1
    assert client.credits_remaining == 42


def test_empty_balance_stops_without_retry(client, sleeps, monkeypatch):
    fake_get(monkeypatch, [FakeResponse(402, {"success": False, "code": "insufficient_credits", "error": "none"})])

    with pytest.raises(LurkAPIError) as caught:
        client.get("/v2/instagram/user/posts", {"username": "nike"})

    assert caught.value.status_code == 402
    assert sleeps == []
    assert client.credits_charged == 0


def test_network_error_is_not_charged(client, monkeypatch):
    fake_get(monkeypatch, [requests.ConnectionError("down")])

    with pytest.raises(LurkAPIError, match="request failed"):
        client.get_user_posts("hunter_bsa")

    assert client.calls == []


def test_missing_credit_amount_is_unknown(client, monkeypatch):
    fake_get(monkeypatch, [FakeResponse(404, {"success": False, "code": "not_found", "error": "missing"})])
    with pytest.raises(LurkAPIError):
        client.get_user_posts("missing")
    assert client.calls[0]["credits_charged"] is None


@pytest.mark.parametrize("body", [{}, {"success": True}, {"success": True, "posts": None}])
def test_malformed_success_does_not_look_like_empty_account(client, monkeypatch, body):
    fake_get(monkeypatch, [FakeResponse(200, body)])
    with pytest.raises(LurkAPIError, match="invalid response"):
        client.get_user_posts("hunter_bsa")
