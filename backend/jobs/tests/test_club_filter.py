import json
from pathlib import Path

import httpx
import pytest
from openai import BadRequestError

from jobs.ai import club_filter
from jobs.tests.conftest import load_fixture

PROMPT_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "club_filter.md"


def _content_risk_error() -> BadRequestError:
    request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
    response = httpx.Response(
        400,
        request=request,
        json={"error": {"message": "Content Exists Risk", "type": "invalid_request_error"}},
    )
    return BadRequestError("Error code: 400 - Content Exists Risk", response=response, body=None)


def test_build_candidates_projects_only_three_fields():
    following = load_fixture("following_sample.json")

    candidates = club_filter.build_candidates(following)

    assert all(set(item.keys()) == {"username", "user_id", "full_name"} for item in candidates)
    assert candidates[0]["user_id"] == following[0]["user_id"]


def test_filter_original_accounts_matches_by_user_id():
    following = load_fixture("following_sample.json")
    ai_clubs = load_fixture("ai_clubs_response_sample.json")["clubs"]

    filtered = club_filter.filter_original_accounts(following, ai_clubs)

    filtered_usernames = {account["username"] for account in filtered}
    assert filtered_usernames == {
        "bcc.hunter",
        "hunterknittedknockers",
        "thebaithakhunter",
        "hunter.hsa",
        "prelawsocietyhc",
        "hunter_altfields_example",
    }
    # The private individual (Roger Coles) must be excluded by the AI decision.
    assert "mysocialdesigner" not in filtered_usernames
    # Filtered records must be the full original records, not the 3-field AI shape.
    assert "profile_pic_url" in filtered[0]


def test_filter_original_accounts_rejects_unknown_ids():
    following = load_fixture("following_sample.json")
    ai_clubs = load_fixture("ai_clubs_response_invalid_sample.json")["clubs"]

    with pytest.raises(ValueError, match="not in the original following file"):
        club_filter.filter_original_accounts(following, ai_clubs)


def test_run_filter_end_to_end_preserves_input_and_writes_expected_clubs(tmp_path, monkeypatch):
    input_path = tmp_path / "following.json"
    following = load_fixture("following_sample.json")
    input_path.write_text(json.dumps(following, ensure_ascii=False), encoding="utf-8")

    ai_response = load_fixture("ai_clubs_response_sample.json")["clubs"]
    monkeypatch.setattr(
        club_filter,
        "classify_with_deepseek",
        lambda candidates, prompt_path: ai_response,
    )

    result = club_filter.run_filter(
        input_path=input_path,
        filtered_output_path=tmp_path / "clubs.json",
        prompt_path=PROMPT_PATH,
    )

    assert result["original_count"] == len(following)
    assert result["ai_club_count"] == len(ai_response)
    assert result["filtered_count"] == len(ai_response)
    assert result["skipped_count"] == 0

    # The original file must never be modified by the filtering step.
    assert json.loads(input_path.read_text(encoding="utf-8")) == following

    # No intermediate files should be created - only the final clubs.json.
    assert set(tmp_path.iterdir()) == {input_path, tmp_path / "clubs.json"}

    filtered_clubs = json.loads((tmp_path / "clubs.json").read_text(encoding="utf-8"))
    assert {account["username"] for account in filtered_clubs} == {
        club["username"] for club in ai_response
    }


def test_run_filter_refuses_to_write_empty_clubs_by_default(tmp_path, monkeypatch):
    input_path = tmp_path / "following.json"
    input_path.write_text(json.dumps(load_fixture("following_sample.json")), encoding="utf-8")
    monkeypatch.setattr(club_filter, "classify_with_deepseek", lambda candidates, prompt_path: [])

    with pytest.raises(ValueError, match="zero clubs"):
        club_filter.run_filter(
            input_path=input_path,
            filtered_output_path=tmp_path / "clubs.json",
            prompt_path=PROMPT_PATH,
        )


def test_classify_with_deepseek_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        club_filter.classify_with_deepseek(
            [{"username": "x", "user_id": "1", "full_name": "X"}], PROMPT_PATH
        )


def test_classify_all_bisects_and_skips_the_flagged_account(monkeypatch):
    candidates = [
        {"username": "a", "user_id": "1", "full_name": "A"},
        {"username": "flagged", "user_id": "2", "full_name": "Flagged Name"},
        {"username": "b", "user_id": "3", "full_name": "B"},
    ]

    def fake_classify(batch, prompt_path):
        if any(item["username"] == "flagged" for item in batch):
            raise _content_risk_error()
        return [
            {"user_id": item["user_id"], "username": item["username"], "is_club": True}
            for item in batch
        ]

    monkeypatch.setattr(club_filter, "classify_with_deepseek", fake_classify)

    ai_clubs, skipped = club_filter.classify_all(candidates, PROMPT_PATH, batch_size=3)

    assert {club["username"] for club in ai_clubs} == {"a", "b"}
    assert skipped == [{"user_id": "2", "username": "flagged"}]
