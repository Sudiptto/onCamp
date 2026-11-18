import json
from pathlib import Path

import pytest

from jobs.post_extraction import club_posts

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_real_duplicate_check(monkeypatch):
    # Tests shouldn't call DeepSeek. By default the AI says "not a duplicate".
    monkeypatch.setattr(club_posts, "judge_same_event_with_deepseek", lambda new_post, candidates: None)
