from jobs.club_discovery import pipeline
from jobs.tests.conftest import load_fixture


class FakeHikerClient:
    """Stands in for HikerClient so this test never makes a network call."""

    def __init__(self, *args, **kwargs):
        pass

    def resolve_user(self, username):
        assert username == "hunterusg"
        return {"pk": "242461848"}

    def get_following(self, user_id):
        assert user_id == "242461848"
        raw_accounts = load_fixture("raw_following_sample.json")
        stats = {
            "endpoint": "/gql/user/following/chunk",
            "pages_fetched": 1,
            "requested_page_size": 50,
            "raw_accounts": len(raw_accounts),
        }
        return raw_accounts, stats


def test_run_discovers_and_writes_public_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "HikerClient", FakeHikerClient)

    result = pipeline.run(college_key="hunter", output_dir=str(tmp_path))

    expected_following = load_fixture("following_sample.json")
    assert result["seed_account"] == "hunterusg"
    assert result["seed_user_id"] == "242461848"
    assert result["following"] == expected_following
    assert result["clubs"] == []
    assert result["refresh_stats"]["public_accounts"] == len(expected_following)
    # One of the eight raw fixture records is private and must be skipped.
    assert result["refresh_stats"]["private_accounts_skipped"] == 1
    assert result["refresh_stats"]["ai_classification"] == "pending"

    written_following = (tmp_path / "following.json").read_text(encoding="utf-8")
    assert "hunterknittedknockers" in written_following
    assert "private_person_example" not in written_following


def test_run_raises_when_seed_account_cannot_be_resolved(monkeypatch):
    class UnresolvableClient(FakeHikerClient):
        def resolve_user(self, username):
            return {}

    monkeypatch.setattr(pipeline, "HikerClient", UnresolvableClient)

    try:
        pipeline.run(college_key="hunter")
    except Exception as exc:  # noqa: BLE001 - asserting on HikerAPIError message
        assert "Could not resolve seed account" in str(exc)
    else:
        raise AssertionError("Expected HikerAPIError when the seed account has no pk/id")
