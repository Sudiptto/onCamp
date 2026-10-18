import json

import pytest

from jobs.post_extraction.pipeline import extract_club_posts, find_club
from jobs.post_extraction.posts import extract_recent_posts
from jobs.tests.conftest import load_fixture


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.requested = []

    def get_user_medias(self, user_id):
        self.requested.append(user_id)
        return self.response


def test_extract_recent_posts_newest_first_and_limited():
    posts = extract_recent_posts(load_fixture("raw_medias_sample.json"), count=2)
    assert [p["post_code"] for p in posts] == ["DdFvIZoDWH-", "DdEAH3mutoM"]
    assert posts[0]["post_url"] == "https://www.instagram.com/p/DdFvIZoDWH-/"
    assert posts[0]["media_type"] == "carousel"


def test_pinned_old_post_does_not_come_first():
    response = {"items": [
        {"pk": "1", "code": "OLD", "1ltaken_at": 1000},
        {"pk": "2", "code": "NEW", "1ltaken_at": 2000},
    ]}
    assert extract_recent_posts(response)[0]["post_code"] == "NEW"


def test_caption_variants():
    response = {"items": [{"pk": "1", "code": "A", "taken_at": 5, "caption": {"text": "hello"}}]}
    assert extract_recent_posts(response)[0]["caption"] == "hello"


@pytest.mark.parametrize("response", [None, {}, {"items": []}, {"items": ["bad", {"no": "pk"}]}, []])
def test_empty_or_malformed_responses(response):
    assert extract_recent_posts(response) == []


def test_extract_club_posts_writes_json(tmp_path):
    client = FakeClient(load_fixture("raw_medias_sample.json"))
    club = {"user_id": "61370581591", "username": "hunter_bsa"}
    result = extract_club_posts(club, output_dir=tmp_path / "posts", count=3, client=client)

    assert client.requested == ["61370581591"]
    saved = json.loads((tmp_path / "posts" / "hunter_bsa.json").read_text(encoding="utf-8"))
    assert saved["post_count"] == 3 == result["post_count"]
    assert saved["raw_response"]["num_results"] == 3


def test_find_club(tmp_path):
    path = tmp_path / "clubs.json"
    path.write_text(json.dumps([{"username": "Hunter_BSA", "user_id": "1"}]), encoding="utf-8")
    assert find_club(path, "hunter_bsa")["user_id"] == "1"
    with pytest.raises(ValueError):
        find_club(path, "missing")
