import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import (
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)

from jobs.ai import club_filter
from jobs.ai.club_filter import IncompleteClassification, MalformedResponseError
from jobs.tests.conftest import load_fixture

PROMPT_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "club_filter.md"
REQUEST = httpx.Request("POST", "https://api.deepseek.com/chat/completions")


def api_error(error_class, status, headers=None):
    response = httpx.Response(status, request=REQUEST, headers=headers, json={"error": {"message": "x"}})
    return error_class("error", response=response, body=None)


def content_risk_error():
    response = httpx.Response(400, request=REQUEST, json={"error": {"message": "Content Exists Risk"}})
    return BadRequestError("Error code: 400 - Content Exists Risk", response=response, body=None)


def candidate(user_id):
    return {"username": f"user{user_id}", "user_id": str(user_id), "full_name": f"User {user_id}"}


@pytest.fixture(autouse=True)
def waits(monkeypatch):
    recorded = []
    monkeypatch.setattr(club_filter.time, "sleep", recorded.append)
    return recorded


class FakeDeepSeek:
    """Plays back a list of replies or errors in place of classify_with_deepseek."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = []

    def __call__(self, batch, prompt_path):
        self.calls.append([item["user_id"] for item in batch])
        step = self.steps[min(len(self.calls), len(self.steps)) - 1]
        if isinstance(step, Exception):
            raise step
        return step


# retries

def test_retries_rate_limit_with_growing_wait(monkeypatch, waits):
    script = FakeDeepSeek(api_error(RateLimitError, 429), api_error(RateLimitError, 429), [{"user_id": "1"}])
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)

    assert club_filter._classify_with_retries([candidate(1)], PROMPT_PATH) == [{"user_id": "1"}]
    assert len(script.calls) == 3
    assert waits == [2.0, 4.0]


def test_retry_after_header_is_capped(monkeypatch, waits):
    script = FakeDeepSeek(
        api_error(RateLimitError, 429, {"retry-after": "7"}),
        api_error(RateLimitError, 429, {"retry-after": "9999"}),
        [],
    )
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)

    club_filter._classify_with_retries([candidate(1)], PROMPT_PATH)
    assert waits == [7.0, club_filter.MAX_RETRY_DELAY_SECONDS]


@pytest.mark.parametrize("error", [
    pytest.param(APITimeoutError(request=REQUEST), id="timeout"),
    pytest.param(api_error(InternalServerError, 503), id="server_error"),
])
def test_retries_timeout_and_server_error(monkeypatch, error):
    script = FakeDeepSeek(error, [])
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)

    club_filter._classify_with_retries([candidate(1)], PROMPT_PATH)
    assert len(script.calls) == 2


def test_raises_after_retry_limit(monkeypatch):
    script = FakeDeepSeek(api_error(InternalServerError, 500))
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)

    with pytest.raises(InternalServerError):
        club_filter._classify_with_retries([candidate(1)], PROMPT_PATH)
    assert len(script.calls) == club_filter.MAX_TRANSIENT_RETRIES + 1


def test_bad_request_is_not_retried(monkeypatch):
    script = FakeDeepSeek(api_error(BadRequestError, 400))
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)

    with pytest.raises(BadRequestError):
        club_filter._classify_batch_safely([candidate(1)], PROMPT_PATH, [])
    assert len(script.calls) == 1


# malformed responses

def test_malformed_json_retries_once_then_raises(monkeypatch):
    script = FakeDeepSeek(MalformedResponseError("not json"))
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)

    with pytest.raises(MalformedResponseError):
        club_filter._classify_with_retries([candidate(1)], PROMPT_PATH)
    assert len(script.calls) == 1 + club_filter.MAX_MALFORMED_RETRIES


def test_malformed_then_valid_reply_succeeds(monkeypatch):
    script = FakeDeepSeek(MalformedResponseError("not json"), [{"user_id": "1"}])
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)

    assert club_filter._classify_with_retries([candidate(1)], PROMPT_PATH) == [{"user_id": "1"}]


def test_classify_with_deepseek_wraps_bad_json(monkeypatch):
    seen = {}
    reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            seen.update(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: reply))

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(club_filter, "OpenAI", FakeOpenAI)

    with pytest.raises(MalformedResponseError):
        club_filter.classify_with_deepseek([candidate(1)], PROMPT_PATH)
    # Our own timeout, and no hidden retries from the library.
    assert seen["timeout"] == club_filter.REQUEST_TIMEOUT_SECONDS
    assert seen["max_retries"] == 0


# classify_all

def test_classify_all_skips_malformed_batch(monkeypatch):
    def fake(batch, prompt_path):
        if batch[0]["user_id"] == "3":
            raise MalformedResponseError("bad")
        return [{"user_id": item["user_id"]} for item in batch]

    monkeypatch.setattr(club_filter, "classify_with_deepseek", fake)
    failed = []

    clubs, _ = club_filter.classify_all(
        [candidate(n) for n in range(1, 7)], PROMPT_PATH, batch_size=2, failed=failed
    )

    assert [club["user_id"] for club in clubs] == ["1", "2", "5", "6"]
    assert failed == [{"user_ids": ["3", "4"], "reason": "malformed response: bad"}]


def test_classify_all_stops_after_retries_run_out(monkeypatch):
    script = FakeDeepSeek([{"user_id": "1"}], api_error(RateLimitError, 429))
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)
    failed = []

    clubs, _ = club_filter.classify_all(
        [candidate(n) for n in (1, 2, 3)], PROMPT_PATH, batch_size=1, failed=failed
    )

    assert [club["user_id"] for club in clubs] == ["1"]
    assert ["3"] not in script.calls  # never tried the batch after the outage
    assert failed[0]["user_ids"] == ["2"]


# cache and progress, using the real following_sample.json

@pytest.fixture
def files(tmp_path):
    following = load_fixture("following_sample.json")
    input_path = tmp_path / "following.json"
    input_path.write_text(json.dumps(following), encoding="utf-8")
    return {
        "following": following,
        "input": input_path,
        "output": tmp_path / "clubs.json",
        "cache": tmp_path / "cache.json",
    }


def patch_deepseek(monkeypatch):
    """Patches in a fake DeepSeek that answers from the fixture and records what it was sent."""
    all_clubs = load_fixture("ai_clubs_response_sample.json")["clubs"]
    asked = []

    def fake(batch, prompt_path):
        ids = {item["user_id"] for item in batch}
        asked.extend(item["user_id"] for item in batch)
        return [club for club in all_clubs if club["user_id"] in ids]

    monkeypatch.setattr(club_filter, "classify_with_deepseek", fake)
    return asked


def run(files, **kwargs):
    return club_filter.run_filter(
        files["input"], files["output"], PROMPT_PATH, cache_path=files["cache"], **kwargs
    )


def test_run_filter_uses_cache_on_second_run(files, monkeypatch):
    asked = patch_deepseek(monkeypatch)

    first = run(files)
    asked.clear()
    second = run(files)

    assert asked == []
    assert (second["classified_count"], second["cached_count"]) == (0, 7)
    assert second["filtered_count"] == first["filtered_count"] == 6


def test_run_filter_sends_only_new_accounts(files, monkeypatch):
    asked = patch_deepseek(monkeypatch)
    run(files)
    asked.clear()

    extra = {"username": "newclub", "user_id": "99", "full_name": "New Club", "is_private": False}
    files["input"].write_text(json.dumps(files["following"] + [extra]), encoding="utf-8")
    run(files)

    assert asked == ["99"]


def test_run_filter_redoes_results_when_model_or_prompt_changes(files, monkeypatch, tmp_path):
    asked = patch_deepseek(monkeypatch)
    run(files)

    asked.clear()
    monkeypatch.setenv("DEEPSEEK_MODEL", "some-other-model")
    run(files)
    assert len(asked) == 7

    asked.clear()
    new_prompt = tmp_path / "prompt.md"
    new_prompt.write_text("a different prompt", encoding="utf-8")
    club_filter.run_filter(files["input"], files["output"], new_prompt, cache_path=files["cache"])
    assert len(asked) == 7


def test_run_filter_resumes_after_failure(files, monkeypatch):
    all_clubs = load_fixture("ai_clubs_response_sample.json")["clubs"]
    asked = []
    outage = {"on": True}

    def fake(batch, prompt_path):
        ids = [item["user_id"] for item in batch]
        asked.append(ids)
        if outage["on"] and len(asked) >= 2:  # an outage keeps failing, even on retries
            raise api_error(RateLimitError, 429)
        return [club for club in all_clubs if club["user_id"] in ids]

    monkeypatch.setattr(club_filter, "classify_with_deepseek", fake)
    files["output"].write_text("OLD CLUBS", encoding="utf-8")

    with pytest.raises(IncompleteClassification) as caught:
        run(files, batch_size=3)

    first_batch = asked[0]
    assert caught.value.missing_count == 4
    assert set(json.loads(files["cache"].read_text(encoding="utf-8"))) == set(first_batch)
    assert files["output"].read_text(encoding="utf-8") == "OLD CLUBS"

    outage["on"] = False
    asked.clear()
    result = run(files, batch_size=3)

    assert sorted(user_id for batch in asked for user_id in batch) == sorted(
        item["user_id"] for item in files["following"] if item["user_id"] not in first_batch
    )
    assert result["filtered_count"] == 6


def test_run_filter_caches_content_filter_rejections(files, monkeypatch):
    all_clubs = load_fixture("ai_clubs_response_sample.json")["clubs"]
    flagged = files["following"][0]["user_id"]
    asked = []

    def fake(batch, prompt_path):
        asked.extend(item["user_id"] for item in batch)
        if any(item["user_id"] == flagged for item in batch):
            raise content_risk_error()
        ids = {item["user_id"] for item in batch}
        return [club for club in all_clubs if club["user_id"] in ids]

    monkeypatch.setattr(club_filter, "classify_with_deepseek", fake)
    first = run(files)
    asked.clear()
    run(files)

    assert first["skipped_count"] == 1
    assert flagged not in asked


def test_run_filter_ignores_unfollowed_cached_clubs(files, monkeypatch):
    patch_deepseek(monkeypatch)
    run(files)

    unfollowed = files["following"][0]["user_id"]
    remaining = [item for item in files["following"] if item["user_id"] != unfollowed]
    files["input"].write_text(json.dumps(remaining), encoding="utf-8")

    result = run(files)

    assert result["original_count"] == 6
    assert unfollowed not in {a["user_id"] for a in json.loads(files["output"].read_text(encoding="utf-8"))}


def test_run_filter_rebuilds_corrupt_cache(files, monkeypatch):
    asked = patch_deepseek(monkeypatch)
    files["cache"].write_text("{not json", encoding="utf-8")

    run(files)

    assert len(asked) == 7
    assert isinstance(json.loads(files["cache"].read_text(encoding="utf-8")), dict)


def test_save_cache_leaves_no_temp_file(files, monkeypatch, tmp_path):
    patch_deepseek(monkeypatch)
    run(files)

    assert {path.name for path in tmp_path.iterdir()} == {"following.json", "clubs.json", "cache.json"}


def test_cache_stores_no_account_details(files, monkeypatch):
    patch_deepseek(monkeypatch)
    run(files)

    text = files["cache"].read_text(encoding="utf-8")
    assert "Burmese Culture Club" not in text
    assert "bcc.hunter" not in text


# rejected requests

@pytest.mark.parametrize("status, error_class, expected", [
    pytest.param(401, AuthenticationError, "check DEEPSEEK_API_KEY", id="401"),
    pytest.param(402, APIStatusError, "out of balance", id="402"),
    pytest.param(404, NotFoundError, "check DEEPSEEK_MODEL", id="404"),
])
def test_classify_all_stops_on_rejected_request(monkeypatch, status, error_class, expected):
    script = FakeDeepSeek(api_error(error_class, status))
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)
    failed = []

    club_filter.classify_all([candidate(n) for n in (1, 2, 3)], PROMPT_PATH, batch_size=1, failed=failed)

    assert len(script.calls) == 1  # not retried, and the other batches were never tried
    assert str(status) in failed[0]["reason"]
    assert expected in failed[0]["reason"]


def test_run_filter_requires_api_key(monkeypatch, files):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        run(files)


def test_run_filter_keeps_progress_on_interrupt(files, monkeypatch):
    calls = []

    def fake(batch, prompt_path):
        calls.append(batch)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return []

    monkeypatch.setattr(club_filter, "classify_with_deepseek", fake)

    with pytest.raises(KeyboardInterrupt):
        run(files, batch_size=3, allow_empty=True)

    assert set(json.loads(files["cache"].read_text(encoding="utf-8"))) == {
        item["user_id"] for item in calls[0]
    }


def test_run_filter_rejects_unknown_user_id(files, monkeypatch):
    script = FakeDeepSeek([{"user_id": "no-such-id"}])
    monkeypatch.setattr(club_filter, "classify_with_deepseek", script)

    with pytest.raises(IncompleteClassification) as caught:
        run(files)

    assert "not in the batch" in caught.value.failed[0]["reason"]
    assert not files["cache"].exists()
    assert not files["output"].exists()


def test_run_filter_keeps_clubs_json_when_zero_clubs(files, monkeypatch):
    monkeypatch.setattr(club_filter, "classify_with_deepseek", lambda batch, path: [])
    files["output"].write_text("OLD CLUBS", encoding="utf-8")

    with pytest.raises(ValueError, match="zero clubs"):
        run(files)

    assert files["output"].read_text(encoding="utf-8") == "OLD CLUBS"


def test_run_filter_handles_missing_user_id(files, monkeypatch):
    asked = patch_deepseek(monkeypatch)
    nameless = {"username": "mystery", "user_id": "", "full_name": ""}
    files["input"].write_text(json.dumps(files["following"] + [nameless]), encoding="utf-8")

    first = run(files)
    asked.clear()
    second = run(files)

    assert first["filtered_count"] == second["filtered_count"] == 6
    assert asked == [""]  # it can't be cached, so it is asked about again, and never selected


def test_run_filter_warns_on_retired_model(files, monkeypatch, capsys):
    patch_deepseek(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

    run(files)

    assert "2026-07-24" in capsys.readouterr().err
