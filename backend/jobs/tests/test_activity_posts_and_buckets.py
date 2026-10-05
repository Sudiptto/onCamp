from datetime import datetime, timedelta, timezone

from jobs.activity_check.buckets import classify_activity
from jobs.activity_check.posts import parse_latest_post
from jobs.tests.conftest import load_fixture

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def test_parse_latest_post_from_real_sample():
    latest = parse_latest_post(load_fixture("raw_medias_sample.json"))

    assert latest["post_id"] == "3982796730936418814"
    assert latest["post_code"] == "DdFvIZoDWH-"
    assert latest["taken_at"] == datetime.fromtimestamp(1789006390, timezone.utc)


def test_parse_latest_post_ignores_item_order_for_pinned_posts():
    response = load_fixture("raw_medias_sample.json")
    response["items"].reverse()  # oldest first, as a pinned old post would appear

    assert parse_latest_post(response)["post_id"] == "3982796730936418814"


def test_parse_latest_post_falls_back_to_pk_snowflake_when_timestamp_missing():
    response = {"items": [{"pk": "3982796730936418814", "code": "x"}]}

    latest = parse_latest_post(response)

    assert latest["taken_at"].date().isoformat() == "2026-09-10"


def test_parse_latest_post_returns_none_without_posts():
    assert parse_latest_post({"items": []}) is None
    assert parse_latest_post({}) is None
    assert parse_latest_post([]) is None


def test_classify_boundaries():
    def bucket(days):
        return classify_activity(NOW - timedelta(days=days), NOW)

    assert bucket(0)["status"] == "active"
    assert bucket(90)["status"] == "active"
    assert bucket(91)["status"] == "inactive"
    assert bucket(90)["check_interval_days"] == 1
    assert bucket(91)["check_interval_days"] == 30


def test_classify_no_posts_is_inactive():
    result = classify_activity(None, NOW)

    assert result["status"] == "inactive"
    assert result["days_since_last_post"] is None
    assert result["check_interval_days"] == 30
