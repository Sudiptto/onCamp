import json
from pathlib import Path

import pytest

from app.models import College
from jobs.club_discovery import semester_refresh


class FakeBlob:
    def __init__(self, container, name):
        self.container = container
        self.name = name

    def exists(self):
        return self.name in self.container.blobs

    def download_blob(self):
        content = self.container.blobs[self.name]

        class FakeDownload:
            def __init__(self, data):
                self.data = data

            def readall(self):
                return self.data

        return FakeDownload(content)


class FakeContainer:
    def __init__(self):
        self.blobs = {}
        self.uploads = []

    def get_blob_client(self, name):
        return FakeBlob(self, name)

    def upload_blob(self, name, data, overwrite):
        assert overwrite is True
        self.blobs[name] = data
        self.uploads.append(name)


def test_run_semester_discovery_refreshes_each_database_college(app, monkeypatch):
    from app.extensions import db as database

    database.session.add_all(
        [
            College(key="baruch", name="Baruch College", seed_account="baruch_sga"),
            College(key="hunter", name="Hunter College", seed_account="hunterusg"),
        ]
    )
    database.session.commit()

    container = FakeContainer()
    discovery_calls = []
    sync_calls = []
    cache_preexisting = []

    def fake_discovery(college_key, college_name, seed_account, output_dir):
        discovery_calls.append((college_key, college_name, seed_account))
        following_path = Path(output_dir) / "following.json"
        following_path.write_text(json.dumps([{"username": f"{college_key}_club"}]), encoding="utf-8")
        return {"seed_account": seed_account}

    def fake_filter(input_path, filtered_output_path, cache_path, **_kwargs):
        assert _kwargs["prompt_path"] == semester_refresh.PROMPT_PATH
        cache_preexisting.append(cache_path.exists())
        clubs = json.loads(Path(input_path).read_text(encoding="utf-8"))
        Path(filtered_output_path).write_text(json.dumps(clubs), encoding="utf-8")
        Path(cache_path).write_text("{}", encoding="utf-8")
        return {"original_count": 1, "filtered_count": 1, "skipped_count": 0}

    monkeypatch.setattr(semester_refresh, "_get_cache_container", lambda: container)
    monkeypatch.setattr(semester_refresh, "run_discovery", fake_discovery)
    monkeypatch.setattr(semester_refresh, "run_filter", fake_filter)
    monkeypatch.setattr(
        semester_refresh,
        "sync_clubs",
        lambda clubs, college_key: sync_calls.append((college_key, clubs)) or {"created": 1},
    )

    result = semester_refresh.run_semester_discovery(app=app)
    repeat_result = semester_refresh.run_semester_discovery(app=app)

    assert [call[0] for call in discovery_calls] == ["baruch", "hunter"] * 2
    assert discovery_calls[0] == ("baruch", "Baruch College", "baruch_sga")
    assert [call[0] for call in sync_calls] == ["baruch", "hunter"] * 2
    assert result["college_count"] == 2
    assert [college["college_key"] for college in result["colleges"]] == ["baruch", "hunter"]
    assert repeat_result["college_count"] == 2
    assert cache_preexisting == [False, False, True, True]
    assert container.uploads == [
        "classifications/baruch.json",
        "classifications/hunter.json",
        "classifications/baruch.json",
        "classifications/hunter.json",
    ]


def test_run_semester_discovery_fails_when_no_colleges_are_configured(app, monkeypatch):
    monkeypatch.setattr(
        semester_refresh,
        "_get_cache_container",
        lambda: pytest.fail("Storage should not be needed when no colleges exist."),
    )

    with pytest.raises(RuntimeError, match="No supported colleges"):
        semester_refresh.run_semester_discovery(app=app)


def test_run_semester_discovery_requires_persistent_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="persistent PostgreSQL"):
        semester_refresh.run_semester_discovery()
