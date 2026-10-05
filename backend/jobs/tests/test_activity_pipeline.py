import json
from datetime import datetime, timezone

from app.services.hiker_client import HikerAPIError
from jobs.activity_check import pipeline
from jobs.tests.conftest import load_fixture

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


class FakeClient:
    """Serves canned medias per user_id and records calls so tests can assert cost."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_user_medias(self, user_id):
        self.calls.append(user_id)
        response = self.responses[user_id]
        if isinstance(response, Exception):
            raise response
        return response


def _write_clubs(tmp_path, clubs):
    path = tmp_path / "clubs.json"
    path.write_text(json.dumps(clubs), encoding="utf-8")
    return path


def test_run_splits_active_inactive_and_errors(tmp_path):
    recent = load_fixture("raw_medias_sample.json")  # newest post 2026-09-10 -> 25 days old
    stale = {"items": [{"pk": "3921934351969666253", "1ltaken_at": 1781751029}]}  # 2026-06-18 -> 109 days
    clubs = [
        {"username": "recent_club", "user_id": "1"},
        {"username": "stale_club", "user_id": "2"},
        {"username": "empty_club", "user_id": "3"},
        {"username": "broken_club", "user_id": "4"},
    ]
    client = FakeClient({
        "1": recent,
        "2": stale,
        "3": {"items": []},
        "4": HikerAPIError("boom"),
    })

    result = pipeline.run(_write_clubs(tmp_path, clubs), tmp_path / "out.json", client=client, now=NOW)

    assert [c["username"] for c in result["active"]] == ["recent_club"]
    assert {c["username"] for c in result["inactive"]} == {"stale_club", "empty_club"}
    assert [e["username"] for e in result["errors"]] == ["broken_club"]
    assert result["active"][0]["last_post_id"] == "3982796730936418814"
    assert result["active"][0]["check_interval_days"] == 1
    assert result["inactive"][0]["check_interval_days"] == 30

    saved = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert saved["active_count"] == 1 and saved["inactive_count"] == 2 and saved["error_count"] == 1


def test_run_limit_only_calls_api_for_first_n_clubs(tmp_path):
    clubs = [{"username": f"c{i}", "user_id": str(i)} for i in range(5)]
    client = FakeClient({str(i): {"items": []} for i in range(5)})

    result = pipeline.run(_write_clubs(tmp_path, clubs), tmp_path / "out.json", limit=2, client=client, now=NOW)

    assert client.calls == ["0", "1"]
    assert result["checked_count"] == 2
