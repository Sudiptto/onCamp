import csv
import json

from jobs.club_discovery.outputs import write_outputs
from jobs.tests.conftest import load_fixture


def test_write_outputs_creates_following_and_clubs_files(tmp_path):
    following = load_fixture("following_sample.json")
    clubs = following[:2]

    paths = write_outputs({"following": following, "clubs": clubs}, output_dir=str(tmp_path))

    following_json = json.loads((tmp_path / "following.json").read_text(encoding="utf-8"))
    clubs_json = json.loads((tmp_path / "clubs.json").read_text(encoding="utf-8"))
    assert following_json == following
    assert clubs_json == clubs
    assert set(paths) == {"following_json", "following_csv", "json", "csv"}

    with open(tmp_path / "following.csv", newline="", encoding="utf-8") as file_handle:
        rows = list(csv.DictReader(file_handle))
    assert rows[0]["username"] == following[0]["username"]
    assert rows[0]["user_id"] == following[0]["user_id"]
    assert list(rows[0].keys()) == [
        "username",
        "user_id",
        "full_name",
        "profile_pic_url",
        "is_private",
    ]


def test_write_outputs_handles_empty_clubs(tmp_path):
    following = load_fixture("following_sample.json")

    write_outputs({"following": following, "clubs": []}, output_dir=str(tmp_path))

    assert json.loads((tmp_path / "clubs.json").read_text(encoding="utf-8")) == []
    with open(tmp_path / "clubs.csv", newline="", encoding="utf-8") as file_handle:
        rows = list(csv.DictReader(file_handle))
    assert rows == []
